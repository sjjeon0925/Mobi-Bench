import io
import os
import json
from datetime import datetime
from agent.base_agent import Agent, AgentInteractionResult, AgentInteractionData
from agent.gemini_cu.cu_agent import CUAgent

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

        # [추가] 환경 데이터셋 규격에 맞는 앱 리스트 세팅
        self.installed_apps = ["Audio_recorder", "Broccoli", "Camera", "Clock", "Contacts", "Expense"]

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
            app_context = f"\n\n[Installed Apps]: {', '.join(self.installed_apps)}"
            instruction = self.instruction + app_context
            cu_res = self.cu_agent.init_task(instruction, screenshot_bytes, "mobile_screen")
            self.is_first_step = False
        else:
            cu_res = self.cu_agent.step(self.last_action, screenshot_bytes, "mobile_screen")

        # 2. 에이전트 응답 -> 벤치마크 액션 매핑 (신규 메소드 호출)
        action_dict, done, success = self._map_cu_res_to_bench(cu_res, width, height)

        # Mobi-Bench 환경 규격에 맞게 최종 딕셔너리 생성
        final_action = {"action_type": action_dict.get("type", "Finish")}
        final_action.update(action_dict)

        # 3. 벤치마크 환경에서 액션 실행
        result = self.env.execute_action(final_action)

        # 4. [핵심] 히스토리 동기화: 에이전트의 기억을 벤치마크의 정답(Default)으로 갱신
        default_action_from_bench = getattr(result, 'default_action', None)

        if default_action_from_bench:
            # 벤치마크 정답 경로를 에이전트 기억 규격으로 변환
            sync_res = self._map_bench_to_cu_res(default_action_from_bench)
            
            # API 히스토리에 이미 기록된 'FunctionCall'의 이름까지 벤치마크 정답으로 바꿉니다.
            if self.cu_agent._contents:
                from google.genai.types import Part, FunctionCall
                
                # 모델의 마지막 응답(Reasoning + FunctionCall)을 가져옴
                last_model_content = self.cu_agent._contents[-1]
                
                # 모델이 읽게 될 본인의 reasoning을 "정답을 따르기로 결정했다"는 내용으로 대체
                sync_action_name = sync_res.get("action", "Finish")
                cleansed_msg = f"Task condition satisfied. I am performing {sync_action_name} as the correct next step."
                
                new_parts = [Part(text=cleansed_msg)]
                
                # 벤치마크 정답이 액션(Click 등)일 경우, 반드시 FunctionCall 파트를 동기화해야 400 에러가 안 남
                if sync_res["type"] == "ACTION":
                    new_parts.append(Part(
                        function_call=FunctionCall(
                            name=sync_res["action"], 
                            args=sync_res["args"]
                        )
                    ))
                
                last_model_content.parts = new_parts

            self.last_action = sync_res
        else:
            # 정답 정보가 없는 경우에만 에이전트의 실제 응답 기록
            self.last_action = cu_res
            # print("\n\t[Warning] 벤치마크 응답에 디폴트 액션이 없어 실제 응답을 기록합니다.\n")

        return AgentInteractionResult(
            done=result.done, 
            success=result.success,
            data=AgentInteractionData(
                instruction=self.instruction, 
                screen=xml,
                reason=cu_res.get("message", ""), 
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
        reasoning = cu_res.get("message", "").lower()

        # [지능적 종료 판단 키워드 설정]
        completion_keys = ["successfully", "done", "finished", "completed", "no more", "deleted", "saved", "all recipes", "no other"]
        verify_keys = ["check", "verify", "ensure", "confirm", "any other", "look for"]

        # 상황 1: 할 일을 다 마치고 앱을 끄거나 뒤로 가려 함 (is_closing)
        is_closing = raw_action in ["go_back", "go_home", "close_current_app"] and \
                     any(k in reasoning for k in completion_keys)
        
        # 상황 2: 완료 직후 "더 있나?" 확인하려고 스크롤 시도 (is_verifying)
        is_verifying = raw_action in ["scroll_at", "swipe"] and \
                       any(k in reasoning for k in verify_keys) and \
                       any(k in reasoning for k in completion_keys)

        # 의도 감지 시 Finish 액션으로 강제 전환
        if is_closing or is_verifying:
            print(f"\n\t[Client Logic] Reasoning에서 완료 및 검증 의도 감지. {raw_action}을 Finish로 매핑합니다.\n")
            return {"type": "Finish", "default": True}, True, True

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
            elif raw_action in ["scroll_at", "scroll_to_text"]:
                x, y = int(args.get("x", 500) * width / 1000), int(args.get("y", 500) * height / 1000)
                # scroll_to_text는 보통 아래로 찾으러 내려가므로 'Down'을 기본값으로 사용
                direction = args.get("direction", "Down").capitalize()
                action_dict = {
                    "action_type": "scroll", 
                    "type": "Swipe", # 정답지의 'Swipe' 타입과 매칭
                    "params": {"direction": direction},
                    "bounds": f"[{x},{y}][{x},{y}]",
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
        
        print(f"\n[GeminiCUAgent] Task Reset: {instruction}")