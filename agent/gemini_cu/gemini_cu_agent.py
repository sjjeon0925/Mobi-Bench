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
        self.installed_apps = ["Audio_recorder", "Settings", "Chrome", "Messages", "Phone", "Broccoli"]

        self.env.results_path = os.path.join(
            "./results", self.name, 
            f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{self.env.parser.name}"
        )
        os.makedirs(self.env.results_path, exist_ok=True)
        self.cu_agent = CUAgent(model_name=model.name, verbose=True)

    def step(self) -> AgentInteractionResult:
        # 1. 환경 데이터 획득
        if self.som_mode == "som":
            screenshot_img, xml = self.env.get_screenshot_with_som()
        else:
            screenshot_img, xml = self.env.get_screenshot_without_som()
        
        # 좌표 변환을 위해 원본 이미지 크기 확인
        width, height = screenshot_img.size
        
        img_byte_arr = io.BytesIO()
        screenshot_img.save(img_byte_arr, format='PNG')
        screenshot_bytes = img_byte_arr.getvalue()

        # 2. 첫 단계일 경우 앱 리스트를 지시문과 합쳐서 전달
        if self.is_first_step:
            app_context = f"\n\n[Installed Apps]: {', '.join(self.installed_apps)}"
            instruction = self.instruction + app_context
            cu_res = self.cu_agent.init_task(instruction, screenshot_bytes, "mobile_screen")
            self.is_first_step = False
        else:
            cu_res = self.cu_agent.step(self.last_action, screenshot_bytes, "mobile_screen")

        self.last_action = cu_res
        
        # 3. 결과 매핑 (Gemini snake_case -> Mobi-Bench PascalCase)
        done = False
        success = False
        action_dict = {}

        if cu_res["type"] == "ACTION":
            raw_action = cu_res["action"]
            args = cu_res["args"]

            # 함수명 및 파라미터 규격 매핑
            if raw_action == "open_app":
                action_dict = {
                    "type": "OpenApp",
                    "params": {"app": args.get("app_name", "")}, # 'app' 키 사용
                    "bounds": None,
                    "default": True
                }
            elif raw_action == "click_at":
                # 0-1000 좌표를 실제 픽셀 bounds로 변환
                x = int(args.get("x", 0) * width / 1000)
                y = int(args.get("y", 0) * height / 1000)
                action_dict = {
                    "type": "Click",
                    "bounds": f"[{x},{y}][{x},{y}]",
                    "params": {},
                    "default": True
                }
            elif raw_action == "wait_5_seconds":
                action_dict = {"type": "Wait", "params": {"seconds": 5}}
            else:
                # 기타 액션들 처리
                action_dict = {"type": raw_action.capitalize(), "params": args}

        elif cu_res["type"] == "RESPONSE":
            # 최종 응답 도달 시 Finish 액션으로 매핑
            action_dict = {"type": "Finish", "default": True}
            done = True
            success = True
        else:
            done = True

        # Mobi-Bench 환경에서 기대하는 최종 딕셔너리 구조 (action_type 키 포함)
        final_action = {"action_type": action_dict.get("type", "Finish")}
        final_action.update(action_dict)

        # [핵심 수정] 환경에 액션을 실제로 실행시킵니다.
        # 이 호출이 있어야 벤치마크 화면이 다음 단계로 넘어갑니다.
        result = self.env.execute_action(final_action)

        # 환경 실행 결과(result.done, result.success)를 반환값에 반영합니다.
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