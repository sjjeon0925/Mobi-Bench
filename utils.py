import re
import json
from verifier_utils import *


def parse_json(raw_response: str) -> dict:
    """
    LLM의 두 가지 주요 출력 형식(순수 JSON, 혼합 텍스트)을 모두 처리하는 최종 파서입니다.
    
    Returns:
        {'Action': dict, 'Reason': str} 형태의 딕셔너리.
    """

    if not isinstance(raw_response, str):
        return {"Action": None, "Reason": None}
    
    cleaned_response = raw_response.strip()

    # --- 전략 1: 전체 문자열이 순수 JSON이라고 가정하고 먼저 파싱 시도 ---
    try:
        # 문자열 전체를 JSON으로 파싱 시도.
        # 이 코드는 문자열이 완벽한 JSON일 때만 성공합니다.
        data = json.loads(cleaned_response)
        
        # 성공 시, 우리가 기대하는 구조로 만들어서 반환
        return {
            "Action": data.get("Action", {}),
            "Reason": data.get("Reason", "")
        }
    except json.JSONDecodeError:
        # 실패했다는 것은 일반 텍스트가 섞여있다는 의미입니다.
        # 따라서 전략 2로 넘어갑니다.
        pass

    # --- 전략 2: 'Reason: ... Action: {...}' 혼합 텍스트를 위한 폴백(Fallback) 로직 ---
    action_keyword = "Action:"
    keyword_index = cleaned_response.rfind(action_keyword)

    if keyword_index == -1:
        # 순수 JSON도 아니고, 'Action:' 키워드도 없으면 전체를 Reason으로 처리
        return {"Action": {}, "Reason": cleaned_response}

    # 'Action:' 키워드를 기준으로 Reason과 Action 분리
    reason_part = cleaned_response[:keyword_index].strip()
    action_part_str = cleaned_response[keyword_index + len(action_keyword):]
    
    if reason_part.lower().startswith("reason:"):
        reason_text = reason_part[len("Reason:"):].strip()
    else:
        reason_text = reason_part

    # Action 부분에서 JSON만 추출하여 파싱
    action_dict = {}
    matches = re.findall(r'\{.*?\}', action_part_str, re.DOTALL)
    if matches:
        try:
            action_dict = json.loads(matches[-1])
        except json.JSONDecodeError:
            pass

    return {
        "Action": action_dict,
        "Reason": reason_text
    }

def generate_numbered_list(data: list, number=False) -> str:
    result_string = ""

    if number:
        for index, item in enumerate(data, start=1):
            if isinstance(item, dict):
                result_string += f"{index}. {json.dumps(item)}\n"
            else:
                result_string += f"{index}. {item}\n"
        return result_string
    else:
        for index, item in enumerate(data, start=1):
            if isinstance(item, dict):
                result_string += f"- {json.dumps(item)}\n"
            else:
                result_string += f"- {item}\n"

        return result_string

# utils/box_annotator.py (또는 바로 코드 안에 포함)

from typing import List, Tuple
from PIL import Image, ImageDraw

class BoxAnnotator:
    def __init__(self, color: Tuple[int, int, int] = (0, 255, 0), thickness: int = 2):
        self.color = color
        self.thickness = thickness

    def annotate(self, image: Image.Image, detections: List[dict]) -> Image.Image:
        draw = ImageDraw.Draw(image)
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            index = det.get("index", "")
            draw.rectangle([x1, y1, x2, y2], outline="green", width=self.thickness)
            if index != "":
                draw.text((x1 + 3, y1 + 3), str(index), fill="black")
        return image