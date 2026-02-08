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
                        part.text = "" #f"Executing {action_name} to fulfill the request."
                    # print("\nchanged\n")
                    
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
        Gemini CU 응답(snake_case) -> Mobi-Bench 액션(PascalCase) 매핑
        지능적 종료 판단 로직 통합 버전
        """
        action_dict = {}
        done = False
        success = False

        raw_action = cu_res.get("action", "")
        # reasoning = cu_res.get("message", "").lower()

        # # [지능적 종료 판단 키워드 설정]
        # completion_keys = ["successfully", "done", "finished", "completed", "no more", "deleted", "saved", "all recipes", "no other"]
        # verify_keys = ["check", "verify", "ensure", "confirm", "any other", "look for"]

        # # 상황 1: 할 일을 다 마치고 앱을 끄거나 뒤로 가려 함 (is_closing)
        # is_closing = raw_action in ["go_back", "go_home", "close_current_app"] and \
        #              any(k in reasoning for k in completion_keys)
        
        # # 상황 2: 완료 직후 "더 있나?" 확인하려고 스크롤 시도 (is_verifying)
        # is_verifying = raw_action in ["scroll_at", "swipe"] and \
        #                any(k in reasoning for k in verify_keys) and \
        #                any(k in reasoning for k in completion_keys)

        # # 의도 감지 시 Finish 액션으로 강제 전환
        # if is_closing or is_verifying:
        #     print(f"\n\t[Client Logic] Reasoning에서 완료 및 검증 의도 감지. {raw_action}을 Finish로 매핑합니다.\n")
        #     return {"type": "Finish", "default": True}, True, True

        # 기본 매핑 로직 시작
        if cu_res.get("type") == "ACTION":
            args = cu_res.get("args", {})

            if not raw_action:
                return {"type": "Finish"}, True, False

            if raw_action == "open_app":
                action_dict = {
                    "type": "OpenApp",
                    "params": {"app": args.get("app_name", "")},
                    "bounds": None,
                    "default": True
                }
            elif raw_action == "click_at":
                x = int(args.get("x", 0) * width / 1000)
                y = int(args.get("y", 0) * height / 1000)
                action_dict = {
                    "type": "Click",
                    "bounds": f"[{x},{y}][{x},{y}]",
                    "params": {},
                    "default": True
                }
            elif raw_action in ["long_press_at", "long_press"]:
                x = int(args.get("x", 0) * width / 1000)
                y = int(args.get("y", 0) * height / 1000)
                action_dict = {
                    "type": "Long Click",
                    "bounds": f"[{x},{y}][{x},{y}]",
                    "params": {},
                    "default": True
                }
            elif raw_action == "type_text_at":
                x = int(args.get("x", 0) * width / 1000)
                y = int(args.get("y", 0) * height / 1000)
                action_dict = {
                    "type": "Input",
                    "params": {"text": args.get("text", "")},
                    "bounds": f"[{x},{y}][{x},{y}]",
                    "default": True
                }
            elif raw_action in ["scroll_at", "scroll_to_text", "swipe"]:
                x = int(args.get("x", 500) * width / 1000)
                y = int(args.get("y", 500) * height / 1000)
                # scroll_to_text는 보통 아래로 찾으러 내려가므로 'Down'을 기본값으로 사용
                direction = args.get("direction", "Down").capitalize()
                action_dict = {
                    "action_type": "scroll", 
                    "type": "Swipe", # 정답지의 'Swipe' 타입과 매칭
                    "params": {"direction": direction},
                    "bounds": f"[{x},{y}][{x},{y}]",
                    "default": True
                }
            elif raw_action == "set_device_setting":
                action_dict = {
                    "type": "OpenApp",
                    "params": {"app": "setting"},
                    "bounds": None,
                    "default": True
                }
            elif raw_action == "go_back":
                action_dict = {
                    "type": "Navigate Back",
                    "params": {},
                    "bounds": "[0,0][0,0]",
                    "default": True
                }
            elif raw_action == "wait_5_seconds":
                action_dict = {"type": "Wait", "params": {"seconds": 5}}
            else:
                # 벤치마크 규격 외 커스텀 액션 처리
                action_dict = {"type": raw_action.replace("_", " ").title(), "params": args}

        elif cu_res.get("type") == "RESPONSE":
            action_dict = {"type": "Finish", "default": True}
            done, success = True, True
        else:
            done = True
        return action_dict, done, success

    def _map_bench_to_cu_res(self, bench_action):
        import re
        # [수정] 벤치마크의 action_type 키를 우선적으로 확인하고 소문자로 처리
        raw_type = bench_action.get("action_type") or bench_action.get("type") or ""
        b_type = str(raw_type).lower().strip()
        
        params = bench_action.get("params", {})
        bounds = bench_action.get("bounds") or ""

        # 좌표 역산 로직 (기존 유지)
        safe_width = self.last_width if self.last_width > 0 else 1080
        safe_height = self.last_height if self.last_height > 0 else 2400
        coords = re.findall(r'\d+', bounds)
        if len(coords) >= 4:
            raw_x = (int(coords[0]) + int(coords[2])) // 2
            raw_y = (int(coords[1]) + int(coords[3])) // 2
            norm_x = int(raw_x * 1000 / safe_width)
            norm_y = int(raw_y * 1000 / safe_height)
        else: norm_x, norm_y = 500, 500

        # [수정 핵심] 벤치마크의 소문자 명칭을 Gemini CU의 함수명(snake_case)으로 매핑
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

        # [중요] 'action' 키에 Gemini가 호출했던 함수 이름과 동일한 값이 들어가야 함
        return {
            "type": "ACTION",
            "action": mapped_action,
            "args": args,
            "message": "Synchronized with benchmark gold standard path."
        }
        
    def reset(self, instruction: str):
        # 부모 클래스의 reset 호출 (self.instruction 저장)
        super().reset(instruction)
        
        # [중요] 새로운 태스크를 위해 에이전트 상태를 완전히 초기화합니다.
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