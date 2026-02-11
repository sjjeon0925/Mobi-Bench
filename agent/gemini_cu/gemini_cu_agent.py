import io
import os
import json
import copy
from datetime import datetime
from agent.base_agent import Agent, AgentInteractionResult, AgentInteractionData
from agent.gemini_cu.cu_agent import CUAgent
from google.genai.types import Part

class GeminiCUAgent(Agent):
    def __init__(self, model, reflection_model, summary_model, env, prompt, 
                 summary_type="post", prompt_type="react", reflection_type="no_reflection", 
                 som_mode="som", save_screenshots=True):
        super().__init__(model, env, "gemini_cu")
        
        self.name = "gemini_cu"
        self.env = env
        self.som_mode = som_mode
        self.is_first_step = True
        self.last_action = None

        self.env.results_path = os.path.join(
            "./results", self.name, 
            f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{self.env.parser.name}"
        )
        os.makedirs(self.env.results_path, exist_ok=True)
        self.cu_agent = CUAgent(model_name=model.name, verbose=True)

    def step(self) -> AgentInteractionResult:
        # 1. 환경 데이터 획득 및 에이전트 실행
        if self.som_mode == "som":
            screenshot_img, xml = self.env.get_screenshot_with_som()
        else:
            screenshot_img, xml = self.env.get_screenshot_without_som()
        
        width, height = screenshot_img.size
        self.last_width, self.last_height = width, height # 역매핑용 저장
        
        img_byte_arr = io.BytesIO()
        screenshot_img.save(img_byte_arr, format='PNG')
        screenshot_bytes = img_byte_arr.getvalue()

        if self.is_first_step:
            cu_res = self.cu_agent.init_task(self.instruction, screenshot_bytes, "mobile_screen")
            self.is_first_step = False
        else:
            cu_res = self.cu_agent.step(self.last_action, screenshot_bytes, "mobile_screen")

        raw_msg = cu_res.get("message")
        original_reasoning = str(raw_msg) if raw_msg is not None else "None"
        
        # 2. 벤치마크 액션 매핑
        action_dict, done, success = self._map_cu_res_to_bench(cu_res, width, height)
        final_action = {"action_type": action_dict.get("type", "Finish")}
        final_action.update(action_dict)

        # 3. 액션 실행
        result = self.env.execute_action(final_action)
        
        # 4. 히스토리 동기화
        default_action_from_bench = getattr(result, 'default_action', None)

        if default_action_from_bench:
            sync_res = self._map_bench_to_cu_res(default_action_from_bench)
            action_name = sync_res.get("action", "finish")

            if self.cu_agent._contents:
                last_model_content = self.cu_agent._contents[-1]
                
                # 새 객체를 생성하지 않고, 기존에 들어있는 Part들을 순회하며 값만 수정합니다.
                for part in last_model_content.parts:
                    # 1. 기존 Reasoning 텍스트 파트의 내용만 교체 (thought_signature 보존)
                    if part.text is not None:
                        part.text = ""
                    
                    # 2. 기존 FunctionCall 파트의 이름과 인자만 교체
                    if part.function_call:
                        part.function_call.name = action_name
                        part.function_call.args = sync_res["args"]
                        
                sync_res["action"] = action_name

            self.last_action = sync_res
        else:
            self.last_action = cu_res
        
        return AgentInteractionResult(
            done=result.done, 
            success=result.success,
            data=AgentInteractionData(
                instruction=self.instruction, 
                screen=xml,
                reason=original_reasoning, # 보존된 원본 텍스트 반환
                action=final_action
            )
        )
        

    def _map_cu_res_to_bench(self, cu_res, width, height):
        """
        Gemini CU 응답 -> Mobi-Bench 액션 매핑
        """
        action_dict = {}
        done = False
        success = False

        # 모델 응답 타입 확인
        msg_type = cu_res.get("type")
        
        if msg_type == "RESPONSE":
            # 대화 종료/완료 응답
            return {"type": "finish", "default": True}, True, True

        elif msg_type == "ACTION":
            raw_action = cu_res.get("action", "")
            args = cu_res.get("args", {})

            if not raw_action:
                return {"type": "finish"}, True, False

            # [1] 좌표 변환 (Gemini의 1000*1000 좌표 응답 -> 실제 픽셀)
            x = int(args.get("x", 0) * width / 1000)
            y = int(args.get("y", 0) * height / 1000)
            bounds_str = f"[{x},{y}][{x},{y}]"

            # [2] 액션 매핑 (Env가 검사하는 핵심 키값 위주로 구성)
            if raw_action == "open_app":
                action_dict = {
                    "type": "openapp",
                    "params": {"app": args.get("app_name", "")}
                }
            elif raw_action == "click_at":
                action_dict = {
                    "type": "click",
                    "bounds": bounds_str
                }
            elif raw_action in ["long_press_at", "long_press"]:
                action_dict = {
                    "type": "long_click",
                    "bounds": bounds_str
                }
            elif raw_action == "type_text_at":
                action_dict = {
                    "type": "input",
                    "bounds": bounds_str,
                    "params": {"text": args.get("text", "")} 
                }
            elif raw_action in ["scroll_at", "scroll_to_text", "swipe"]:
                action_dict = {
                    "type": "scroll" 
                }
            elif raw_action == "go_back":
                action_dict = {
                    "type": "navigate_back"
                }
            elif raw_action == "go_home":
                action_dict = {
                    "type": "navigate_home"
                }
            elif raw_action == "wait_5_seconds":
                action_dict = {
                    "type": "wait",
                    "params": {"seconds": 5}
                }
            else:
                # 그 외 커스텀 액션 (Unknown)
                action_dict = {"type": raw_action, "params": args}

        else:
            # 에러나 기타 상태 -> 종료 처리
            done = True

        return action_dict, done, success

    def _map_bench_to_cu_res(self, bench_action):
        import re
        # 벤치마크의 action_type 키를 우선적으로 확인하고 소문자로 처리
        raw_type = bench_action.get("action_type") or bench_action.get("type") or ""
        b_type = str(raw_type).lower().strip()
        
        params = bench_action.get("params", {})
        bounds = bench_action.get("bounds") or ""

        # 좌표 역산 로직
        safe_width = self.last_width if self.last_width > 0 else 1080
        safe_height = self.last_height if self.last_height > 0 else 2400
        coords = re.findall(r'\d+', bounds)
        if len(coords) >= 4:
            raw_x = (int(coords[0]) + int(coords[2])) // 2
            raw_y = (int(coords[1]) + int(coords[3])) // 2
            norm_x = int(raw_x * 1000 / safe_width)
            norm_y = int(raw_y * 1000 / safe_height)
        else: norm_x, norm_y = 500, 500

        # 벤치마크의 소문자 명칭을 Gemini CU의 함수명으로 매핑
        if b_type in ["openapp", "open_app"]:
            mapped_action = "open_app"
            args = {"app_name": params.get("app", "")}
        elif b_type in ["click", "click_at"]:
            mapped_action = "click_at"
            args = {"x": norm_x, "y": norm_y}
        elif b_type in ["long click", "long_click", "long_press_at"]:
            mapped_action = "long_press_at"
            args = {"x": norm_x, "y": norm_y}
        elif b_type in ["input", "type_text_at"]:
            mapped_action = "type_text_at"
            args = {"x": norm_x, "y": norm_y, "text": params.get("text", "")}
        elif b_type in ["swipe", "scroll_at"]:
            mapped_action = "scroll_at"
            args = {"x": norm_x, "y": norm_y, "direction": params.get("direction", "").lower()}
        elif b_type in ["Navigate Back", "go_back"]:
            mapped_action = "go_back"
            args = {}
        elif b_type == "finish":
            return {"type": "RESPONSE", "message": "Task completed successfully."}
        else:
            mapped_action = b_type
            args = params

        # 'action' 키에 Gemini가 호출했던 함수 이름과 동일한 값이 들어가야 함
        return {
            "type": "ACTION",
            "action": mapped_action,
            "args": args,
            "message": "Synchronized with benchmark gold standard path."
        }
        
    def reset(self, instruction: str):
        # 부모 클래스의 reset 호출 (self.instruction 저장)
        super().reset(instruction)
        
        # 새로운 태스크를 위해 에이전트 상태를 완전히 초기화
        self.is_first_step = True
        self.last_action = None
        
        # 필요 시 CUAgent 내부 히스토리 강제 초기화 (init_task에서 수행되지만 안전을 위해)
        if hasattr(self, 'cu_agent'):
            self.cu_agent._contents = [] 

            # 누적된 요약본 초기화
            self.cu_agent.history_summary = ""
            
            # 지시사항 백업 초기화
            self.cu_agent._instruction = instruction
        
        print(f"\n[GeminiCUAgent] Task Reset: {instruction}")