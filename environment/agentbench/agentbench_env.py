import re
from environment.base_env import Env, EnvInteractionResult
from screen_parser.base_parser import Parser
import xml.etree.ElementTree as ET
from PIL import Image
from typing import Tuple
from openai import OpenAI
import json, os
import numpy as np

class AgentBenchEnv(Env):
    def __init__(self, parser: Parser, name: str):
        super().__init__(parser, name)
        self.task_dir = None
        self.current_step = 0
        self.curr_xml = None
        self.curr_screenshot_size = (1080, 2400)  # Will store (width, height) of current 
        self.reset()
        self.parser= parser
        self.results_path = None
        self.app_dir = ""
        self.task_name = ""
        self.default_counter = 0
        self.finish_default_counter = 0
        self.finish_mismatch_counter = 0
        self.reflection_stats = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
        # API 키 환경 변수에서 로드 (OpenAI 전용)
        # api_key = os.environ.get("OPENAI_API_KEY")
        
        # if not api_key:
        #     raise ValueError(
        #         "OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.\n"
        #         "OpenAI API 키를 OPENAI_API_KEY 환경 변수에 설정해주세요."
        #     )
            
        # self.openai_client = OpenAI(api_key=api_key)
        self.openai_client = None


    def reset(self):
        # reset all files
        self.xmls = []
        self.screenshots = []
        self.raw_actions = []
        self.current_step = 0
        self.success_actions = []
        self.reflection_stats = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}

    def load_task(self, task_dir: str):
        # Load XMLs and screenshots
        print("loading task", task_dir)
        self.reset()
        self.task_dir = task_dir
        self.app_name = os.path.basename(os.path.dirname(task_dir))
        step = 0
        while True:
            try:
                # -------------------- #
                with open(f"{task_dir}/{step}.xml", "r", encoding='utf-8') as f:
                    self.xmls.append(f.read())
                    print(f"Loaded XML for step {step}")
                self.screenshots.append(f"{task_dir}/{step}.png")
                with open(f"{task_dir}/{step}_answers.json", "r", encoding='utf-8') as f:
                    self.raw_actions.append(f.read())
                step += 1
            except FileNotFoundError:
                break
        return step



    def scale_point(self, point, ref_resolution: Tuple[int, int]):
        if self.curr_screenshot_size:
            orig_width, orig_height = self.curr_screenshot_size
            x = int(point[0] * orig_width / ref_resolution[0])
            y = int(point[1] * orig_height / ref_resolution[1])
            return (x, y)
        return point

    def _is_point_in_bounds(self, point, bounds, scale_point=False):
        # Convert bounds string "[x1,y1][x2,y2]" to coordinates
        coords = bounds.strip('[]').split('][')
        x1, y1 = map(int, coords[0].split(','))
        x2, y2 = map(int, coords[1].split(','))

        x, y = point
        if scale_point and self.curr_screenshot_size:
            # Extract reference resolution from raw action
            resolution_pattern = r"Screen Resolution \((\d+),\s*(\d+)\)"
            raw_action = self.raw_actions[self.current_step]
            resolution_match = re.search(resolution_pattern, raw_action)
            ref_width, ref_height = map(int, resolution_match.groups()) if resolution_match else (320, 720)

            # Scale up from reference resolution to actual screenshot size
            orig_width, orig_height = self.curr_screenshot_size
            x = int(x * orig_width / ref_width)
            y = int(y * orig_height / ref_height)
            scaled_point = (x, y)
            print("scaled_point: ", scaled_point)
            print("bounds: ", bounds)
        return x1 <= x <= x2 and y1 <= y <= y2

    def get_xml(self) -> Tuple[str, str]:
        print(f"Getting XML for step {self.current_step}, total steps: {len(self.xmls)-1}")
        print(f"current instruction: {self.task_name}\n, current step: {self.current_step}")
        raw_xml = self.xmls[self.current_step]
        parsed_xml = self.parser.parse(raw_xml)
        self.curr_xml = parsed_xml

        # Get screenshot size for coordinate scaling
        with Image.open(self.screenshots[self.current_step]) as img:
            self.curr_screenshot_size = img.size

        #return raw_xml, parsed_xml
        return raw_xml, self.curr_xml

    def get_screenshot(self) -> Image:
        screenshot_path = self.screenshots[self.current_step]
        return Image.open(screenshot_path)

    def get_screenshot_with_som(self) -> Tuple[Image.Image, str]:
        print(f"Getting screenshot with SOM for step {self.current_step}, total steps: {len(self.screenshots)-1}")
        raw_screenshot_path = self.screenshots[self.current_step]
        raw_screenshot = Image.open(raw_screenshot_path)

        raw_xml = self.xmls[self.current_step]

        screenshot, ui_elements = self.parser.SoM(raw_screenshot, raw_xml)
        self.curr_xml = ui_elements

        with Image.open(raw_screenshot_path) as img:
            self.curr_screenshot_size = img.size

        return screenshot, ui_elements

    def get_screenshot_without_som(self) -> Tuple[Image.Image, str]:
        """Return raw screenshot and parsed XML without overlays (NoSoM)."""
        print(f"Getting screenshot without SOM for step {self.current_step}, total steps: {len(self.screenshots)-1}")
        raw_screenshot_path = self.screenshots[self.current_step]
        raw_screenshot = Image.open(raw_screenshot_path)

        raw_xml = self.xmls[self.current_step]
        # UI_caption parser needs a SoM pass to populate view_elements/index-bounds mapping.
        if getattr(self.parser, "name", "") == "UI_caption":
            _, parsed_xml = self.parser.SoM(raw_screenshot, raw_xml)
        else:
            parsed_xml = self.parser.parse(raw_xml)
        self.curr_xml = parsed_xml

        with Image.open(raw_screenshot_path) as img:
            self.curr_screenshot_size = img.size

        return raw_screenshot, parsed_xml


    def _parse_bounds(self, bounds_str: str) -> list[int] | None:
        """'[x1,y1][x2,y2]' 형식의 문자열을 [x1, y1, x2, y2] 리스트로 변환합니다."""
        if not isinstance(bounds_str, str):
            return None
        # 정규식을 사용하여 숫자 4개를 추출
        numbers = re.findall(r'\d+\.?\d*', bounds_str)
        if len(numbers) == 4:
            return [n for n in numbers]
        return None

    def _is_bounds_contained(self, inner_bounds_str: str, outer_bounds_str: str) -> bool:
        """inner_bounds의 중심점이 outer_bounds 안에 포함되는지 확인합니다."""
        inner = self._parse_bounds(inner_bounds_str)
        outer = self._parse_bounds(outer_bounds_str)

        print("inner:", inner_bounds_str, inner)
        print("outer:", outer_bounds_str, outer)

        if inner and outer:
            # 중심점 좌표 계산
            try:
                inner = list(map(float, inner))
                outer = list(map(float, outer))
            except ValueError:
                print("Invalid bounds for float conversion.")
                return False

            center_x = (inner[0] + inner[2]) / 2
            center_y = (inner[1] + inner[3]) / 2

            is_center_inside = (outer[0] <= center_x <= outer[2] and
                                outer[1] <= center_y <= outer[3])
            return is_center_inside
        return False

    # --- 메인 평가 함수 ---

    # def _get_cosine_similarity(self, text1: str, text2: str) -> float:
    #     """OpenAI 임베딩을 사용해 두 텍스트의 코사인 유사도를 계산합니다."""
    #     if not text1 or not text2:
    #         # 두 텍스트가 모두 비어있을 때만 1.0 (일치) 반환
    #         return 1.0 if text1 == text2 else 0.0
    #     try:
    #         response = self.openai_client.embeddings.create(
    #             input=[text1, text2],
    #             model="text-embedding-3-large"
    #         )
    #         embedding1 = np.array(response.data[0].embedding)
    #         embedding2 = np.array(response.data[1].embedding)
            
    #         dot_product = np.dot(embedding1, embedding2)
    #         norm1 = np.linalg.norm(embedding1)
    #         norm2 = np.linalg.norm(embedding2)
            
    #         # 0으로 나누는 오류 방지
    #         if norm1 == 0 or norm2 == 0:
    #             return 0.0
                
    #         return dot_product / (norm1 * norm2)
    #     except Exception as e:
    #         print(f"Cosine similarity API error: {e}")
    #         return 0.0
    def _get_cosine_similarity(self, text1: str, text2: str) -> float:
        """OpenAI API를 쓰지 않고 단순 문자열 비교로 대체합니다 (방법 B)."""
        if not text1 or not text2:
            return 1.0 if text1 == text2 else 0.0

        # 문자열 양끝 공백 제거 및 대소문자 무시 비교
        if text1.strip().lower() == text2.strip().lower():
            return 1.0  # 완벽히 일치하면 유사도 100% 반환

        return 0.0  # 틀리면 0% 반환

    # Lightweight matcher for reflection logging (no file logs)
    def _evaluate_action_match(self, action_obj, raw_actions):
        if not action_obj or not raw_actions:
            return False
        predicted_type = action_obj.get('action_type')
        if isinstance(predicted_type, str):
            predicted_type = predicted_type.lower().replace(' ', '_')
            if predicted_type == 'open_app':
                predicted_type = 'openapp'
        for answer_action in raw_actions:
            answer_type = answer_action.get('type', '').lower().replace(' ', '_')
            if answer_type == 'swipe':
                answer_type = 'scroll'
            if answer_type == 'open_app':
                answer_type = 'openapp'
            if predicted_type != answer_type:
                continue
            if predicted_type == 'openapp':
                return True
            if predicted_type in ['click', 'long_click', 'input']:
                bbox = action_obj.get('bounds') or action_obj.get('bbox')
                if bbox is None and action_obj.get('index') not in (None, {}, -1):
                    elem = self.parser.find_element_by_index(action_obj.get('index'))
                    if elem is not None:
                        bbox = elem.get('bounds')
                if bbox is None and action_obj.get('coordinates'):
                    try:
                        x, y = action_obj['coordinates']
                        bbox = f"[{int(x)},{int(y)}][{int(x)},{int(y)}]"
                    except Exception:
                        bbox = None
                if self._is_bounds_contained(str(bbox), answer_action.get('bounds')):
                    if predicted_type == 'input':
                        pred_text = ''
                        if isinstance(action_obj.get('params'), dict):
                            pred_text = action_obj.get('params', {}).get('text', '')
                        if pred_text == answer_action.get('params', {}).get('text', ''):
                            return True
                    else:
                        return True
            else:
                return True
        return False

    def execute_action(self, predicted_action: dict) -> 'EnvInteractionResult':
        """
        주어진 액션(predicted_action)과 정답 액션 리스트(raw_actions)를 비교하여 매칭 여부를 반환합니다.
        모든 print 출력을 지정된 로그 파일에 함께 기록합니다.
        """
        if predicted_action == None:
            self.success_actions.append(0)
            if(self.current_step >= len(self.raw_actions)):
                return EnvInteractionResult(success=False, done=True)
            else:
                # predicted_action이 없을 때는 default_action을 생성하지 않고 None으로 반환
                return EnvInteractionResult(success=False,
                                    done=False, 
                                    default_action=None,
                                    feedback=None)
            
        # 로그 파일을 추가 모드('a')로 열고, 인코딩을 'utf-8'로 설정합니다.
        # 이렇게 하면 함수가 호출될 때마다 파일 끝에 로그가 추가됩니다.
        os.makedirs(self.results_path, exist_ok=True)  # results_path가 없으면 생성
        log_file = os.path.join(self.results_path, '_action_matching_log.txt')

        with open(log_file, 'a', encoding='utf-8') as f:
            raw_actions = json.loads(self.raw_actions[self.current_step]) if self.current_step < len(self.raw_actions) else []
            reflection_info = predicted_action.pop('reflection_info', None)
            
            # 1. 기본(Default) 액션 처리 (요구사항: 무조건 첫 번째 액션)
            default_action = {}
            if raw_actions:
                selected_action = None
                for act in raw_actions:
                    if act.get('default', False):
                        selected_action = act
                        break
                
                # 없으면 첫 번째 액션 사용
                if not selected_action:
                    selected_action = raw_actions[0]

                action_type_normalized = selected_action['type'].lower().replace(' ', '_')
                if action_type_normalized == 'swipe':  # Swipe를 scroll로 통일
                    action_type_normalized = 'scroll'

                default_action['action_type'] = action_type_normalized
                default_action['bounds'] = selected_action.get('bounds', None)
                default_action['params'] = selected_action.get('params', {})
                default_action['index'] = selected_action.get('index')

            msg1 = f"--- Default Action Determined ---"
            print(msg1)
            f.write(msg1 + '\n')

            msg2 = f"Default Action: {default_action}, bbox: {default_action.get('bounds')}"
            print(msg2)
            f.write(msg2 + '\n')

            msg3 = "-" * 30
            print(msg3)
            f.write(msg3 + '\n')

            # 2. 주어진 액션과 정답 액션 리스트 비교
            matches = False
            predicted_type = predicted_action.get('action_type')
            # normalize predicted type
            if isinstance(predicted_type, str):
                predicted_type = predicted_type.lower().replace(' ', '_')
                # unify open_app -> openapp to match dataset 'OpenApp'
                if predicted_type == 'open_app':
                    predicted_type = 'openapp'

            msg4 = f"--- Matching Predicted Action ---"
            print(msg4)
            f.write(msg4 + '\n')

            msg5 = f"Predicted Action: {predicted_action}"
            print(msg5)
            f.write(msg5 + '\n')

            msg6 = "-" * 30
            print(msg6)
            f.write(msg6 + '\n')
            
            for i, answer_action in enumerate(raw_actions):
                loop_msg1 = f"\n[Loop {i+1}] Comparing with Answer Action: {answer_action}"
                print(loop_msg1)
                f.write(loop_msg1 + '\n')

                # 타입 정규화 ("Long Click" -> "long_click", "Swipe" -> "scroll")
                answer_type = answer_action['type'].lower().replace(' ', '_')
                if answer_type == 'swipe':
                    answer_type = 'scroll'
                if answer_type == 'open_app':
                    answer_type = 'openapp'

                # a. 타입이 일치하지 않으면 다음 액션으로 넘어감
                if predicted_type == "long_click" and answer_type == "click":
                    loop_msg_temp = f" -> Click type Allowance: Predicted ('{predicted_type}') vs Answer ('{answer_type}')"
                    print(loop_msg_temp)
                    f.write(loop_msg_temp + '\n')

                elif predicted_type != answer_type:
                    loop_msg2 = f"  -> Type Mismatch: Predicted ('{predicted_type}') vs Answer ('{answer_type}')"
                    print(loop_msg2)
                    f.write(loop_msg2 + '\n')
                    continue
                
                loop_msg3 = f"  -> Type Match: '{predicted_type}'"
                print(loop_msg3)
                f.write(loop_msg3 + '\n')
                
                # b. 타입이 일치하면 세부 조건 비교
                current_match = False
                if predicted_type in ['click', 'long_click']:
                    bbox = predicted_action.get('bounds', None)
                    if bbox is None:
                        bbox = predicted_action.get('bbox', None)
                    if bbox is None:
                        elem = None
                        if predicted_action.get('index') is not None and not isinstance(predicted_action.get('index'), dict):
                            elem = self.parser.find_element_by_index(predicted_action.get('index'))
                        bbox = elem.get('bounds') if elem is not None else None
                    # image-only: if we only have coordinates, treat them as a point bbox
                    if bbox is None and predicted_action.get('coordinates'):
                        try:
                            x, y = predicted_action['coordinates']
                            bbox = f"[{int(x)},{int(y)}][{int(x)},{int(y)}]"
                        except Exception:
                            bbox = None
                    current_match = self._is_bounds_contained(
                        str(bbox), 
                        answer_action.get('bounds')
                    )
                    loop_msg4 = f"  -> Bounds Check: {'MATCH' if current_match else 'NO MATCH'}"
                    print(loop_msg4)
                    f.write(loop_msg4 + '\n')
                    if current_match:
                        if answer_action.get('default', False):
                            self.default_counter += 1
                            print(f"Default action matched {self.default_counter} times.")
                            f.write(f"Default action matched {self.default_counter} times.\n")
                    # if(predicted_action.get('index') == answer_action.get('index')):
                    #     current_match = True

                elif predicted_type == 'input':
                    bbox = predicted_action.get('bounds') or predicted_action.get('bbox')
                    if bbox is None:
                        element_obj = None
                        if predicted_action.get('index') is not None and not isinstance(predicted_action.get('index'), dict):
                            element_obj = self.parser.find_element_by_index(predicted_action.get('index'))
                        bbox = element_obj.get('bounds') if element_obj else None
                    # image-only: if only coordinates are provided, build a point bbox
                    if bbox is None and predicted_action.get('coordinates'):
                        try:
                            x, y = predicted_action['coordinates']
                            bbox = f"[{int(x)},{int(y)}][{int(x)},{int(y)}]"
                        except Exception:
                            bbox = None
                    
                    bounds_match = self._is_bounds_contained(str(bbox), answer_action.get('bounds'))
                    
                    # 텍스트 유사도 비교 로직
                    predicted_params = predicted_action.get('params', "")
                    if isinstance(predicted_params, dict):
                        predicted_text = predicted_params.get('text', "")
                    else:
                        predicted_text = predicted_params or ""
                    if not predicted_text:
                        predicted_text = predicted_action.get('text', "")
                    answer_params = answer_action.get('params', {})
                    answer_text = ""
                    if isinstance(answer_params, dict):
                        answer_text = answer_params.get('text', "")
                    elif isinstance(answer_params, str):
                        answer_text = answer_params
                    
                    similarity_score = self._get_cosine_similarity(predicted_text, answer_text)
                    text_match = similarity_score >= 0.7 # 70% 이상이면 매치
                    
                    current_match = bounds_match and text_match
                    
                    loop_msg5 = f"  -> Bounds Check: {'MATCH' if bounds_match else 'NO MATCH'}"
                    print(loop_msg5)
                    f.write(loop_msg5 + '\n')
                    
                    # 로그에 유사도 지수까지 함께 기록하여 디버깅 용이성 향상
                    loop_msg6 = f"  -> Text Check: {'MATCH' if text_match else 'NO MATCH'} (Similarity: {similarity_score:.4f})"
                    print(loop_msg6)
                    f.write(loop_msg6 + '\n')
                    
                    if current_match and answer_action.get('default', False):
                        self.default_counter += 1
                        print(f"Default action matched {self.default_counter} times.")
                        f.write(f"Default action matched {self.default_counter} times." + '\n')
                    
                elif predicted_type == 'scroll':
                    current_match = True
                    loop_msg7 = f"  -> Direction Check: {'MATCH' if current_match else 'NO MATCH'}"
                    print(loop_msg7)
                    f.write(loop_msg7 + '\n')
                    if current_match:
                        if answer_action.get('default', False):
                            self.default_counter += 1
                            print(f"Default action matched {self.default_counter} times.")
                            f.write(f"Default action matched {self.default_counter} times.\n")

                elif predicted_type in ['navigate_back', 'finish']:
                    # 타입이 일치하는 것만으로 충분함
                    current_match = True
                    if predicted_type == 'finish' and answer_type != 'finish':
                        self.finish_mismatch_counter += 1
                        mismatch_msg = f"Finish action mismatch count: {self.finish_mismatch_counter}"
                        print(mismatch_msg)
                        f.write(mismatch_msg + '\n')
                elif predicted_type == 'openapp':
                    # Policy: For OpenApp, only the action type matters.
                    # If the model predicted openapp and the answer type is openapp, count as MATCH regardless of params.
                    current_match = True
                    loop_msg_open = "  -> OpenApp: type matched; app_name ignored (counted as MATCH)"
                    print(loop_msg_open)
                    f.write(loop_msg_open + '\n')
                    if current_match and answer_action.get('default', False):
                        self.default_counter += 1
                        print(f"Default action matched {self.default_counter} times.")
                        f.write(f"Default action matched {self.default_counter} times.\n")
                    loop_msg8 = "  -> Match by type definition."
                    print(loop_msg8)
                    f.write(loop_msg8 + '\n')
                    if predicted_type == 'finish':
                        self.finish_default_counter += 1
                        print(f"Finish action matched {self.finish_default_counter} times.")
                        f.write(f"Finish action matched {self.finish_default_counter} times.\n")
                    else:
                        if answer_action.get('default', False):
                            self.default_counter += 1
                            print(f"Default action matched {self.default_counter} times.")
                            f.write(f"Default action matched {self.default_counter} times.\n")

                if current_match:
                    matches = True
                    loop_msg9 = "  --> Match found! Breaking loop."
                    print(loop_msg9)
                    f.write(loop_msg9 + '\n')
                    break # 매칭되는 첫 번째 액션을 찾으면 루프 종료
            
            final_msg1 = "\n" + "="*30
            print(final_msg1)
            f.write(final_msg1 + '\n')
            
            final_msg2 = f"Final Matching Result: {matches}"
            print(final_msg2)
            f.write(final_msg2 + '\n')

            final_msg3 = f"=============================="
            print(final_msg3)
            f.write(final_msg3 + '\n')

            # Reflection logging (if provided)
            if reflection_info:
                pre_action = reflection_info.get('pre_action')
                post_action = reflection_info.get('post_action', predicted_action)
                verdict = reflection_info.get('verdict')
                pre_match = self._evaluate_action_match(pre_action, raw_actions)
                post_match = matches

                f.write(f"Reflection pre_action: {json.dumps(pre_action, ensure_ascii=False)}\n")
                f.write(f"Reflection verdict(correct?): {verdict}\n")
                f.write(f"Reflection post_action: {json.dumps(post_action, ensure_ascii=False)}\n")
                f.write(f"Pre-action match: {pre_match}, Post-action match: {post_match}\n")

                if verdict is True and post_match:
                    self.reflection_stats["tp"] += 1
                elif verdict is False and not post_match:
                    self.reflection_stats["tn"] += 1
                elif verdict is True and not post_match:
                    self.reflection_stats["fp"] += 1
                elif verdict is False and post_match:
                    self.reflection_stats["fn"] += 1

                ref_log_path = os.path.join(self.results_path, "reflection.txt")
                os.makedirs(self.results_path, exist_ok=True)
                with open(ref_log_path, 'a', encoding='utf-8') as rf:
                    rf.write(json.dumps({
                        "step": self.current_step,
                        "instruction": getattr(self, "instruction", None),
                        "verdict": verdict,
                        "pre_action": pre_action,
                        "post_action": post_action,
                        "pre_match": pre_match,
                        "post_match": post_match,
                        "stats": self.reflection_stats
                    }, ensure_ascii=False) + ',\n')

                if (self.current_step + 1) % 10 == 0:
                    summary_msg = (f"[Reflection stats] TP={self.reflection_stats['tp']}, "
                                   f"TN={self.reflection_stats['tn']}, "
                                   f"FP={self.reflection_stats['fp']}, "
                                   f"FN={self.reflection_stats['fn']}")
                    print(summary_msg)
                    f.write(summary_msg + '\n')

            # No extra matching timing (simplified per request)

        # with 블록이 여기서 끝나므로 파일은 자동으로 닫힙니다.
        # 아래는 기존 로직을 그대로 유지합니다.
        self.current_step += 1
        if matches:
            self.success_actions.append(1)
            if(self.current_step >= len(self.raw_actions)):
                if(0 in self.success_actions):
                    return EnvInteractionResult(success=False, done=True)
                else:
                    return EnvInteractionResult(success=True, done=True)
        else:
            self.success_actions.append(0)
            if(self.current_step >= len(self.raw_actions)):
                return EnvInteractionResult(success=False, done=True)
            
        return EnvInteractionResult(success=matches, 
                                    done=False, 
                                    default_action=default_action if default_action else None,
                                    feedback=None)
