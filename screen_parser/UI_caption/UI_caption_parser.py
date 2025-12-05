import os
import json
import time
import base64
import io
from typing import Tuple, Any

import cv2
import numpy as np
import torch
import easyocr
from PIL import Image, ImageDraw, ImageFont
from transformers import AutoProcessor, AutoModelForCausalLM
from ultralytics import YOLO
from torchvision.transforms import ToPILImage
from torchvision.ops import box_convert
from supervision.detection.core import Detections
from supervision.draw.color import ColorPalette

from screen_parser.base_parser import Parser
from utils import BoxAnnotator


class UICaptionParser(Parser):
    def __init__(self):
        super().__init__("UI_caption")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Models (local paths under screen_parser/UI_caption/)
        self.yolo = YOLO("screen_parser/UI_caption/icon_detect/model.pt")  # icon detector
        self.processor = AutoProcessor.from_pretrained(
            "microsoft/Florence-2-base", trust_remote_code=True
        )
        self.caption_model = AutoModelForCausalLM.from_pretrained(
            "screen_parser/UI_caption/icon_caption",
            trust_remote_code=True,
            torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
        ).to(self.device)

        self.ocr = easyocr.Reader(["en"])
        self.annotator = BoxAnnotator(color=ColorPalette.DEFAULT)
        self.view_elements = []

    def parse(self, raw_xml: str) -> str:
        # XML is ignored; descriptions are built from self.view_elements
        return self._make_description()

    def SoM(self, screenshot: Image.Image, raw_xml: str) -> Tuple[Image.Image, str]:
        """
        OCR + YOLO + caption to produce element list and annotated image.
        """
        t0 = time.time()

        # 1. OCR
        ocr_result = self.ocr.readtext(np.array(screenshot), text_threshold=0.8)
        ocr_texts = [str(item[1]) for item in ocr_result]
        ocr_bboxes = [
            [int(item[0][0][0]), int(item[0][0][1]), int(item[0][2][0]), int(item[0][2][1])]
            for item in ocr_result
        ]

        # 2. YOLO icon detection
        w, h = screenshot.size
        yolo_output = self.yolo.predict(screenshot, imgsz=(h, w), conf=0.05, verbose=False)[0]
        icon_bboxes = yolo_output.boxes.xyxy.cpu().numpy().tolist()
        icon_bboxes = [
            {"type": "icon", "bounds": box, "interactivity": True, "content": None}
            for box in icon_bboxes
        ]

        # 3. Merge OCR + YOLO, remove heavy overlaps
        ocr_bboxes = [
            {"type": "text", "bounds": box, "interactivity": False, "content": text}
            for box, text in zip(ocr_bboxes, ocr_texts)
        ]
        elements = self._remove_overlap(icon_bboxes, ocr_bboxes)

        # 4. Caption icons with Florence-2
        elements = self._generate_captions(elements, screenshot)

        # 5. Save elements
        self.view_elements = elements

        # 6. Annotated image + description
        annotated = self._draw_boxes(screenshot.copy(), elements)
        elapsed = time.time() - t0
        print(f"[UI_caption] SoM parsing time: {elapsed:.2f}s")
        return annotated, self._make_description()

    def find_element_by_index(self, index: int) -> dict:
        for element in self.view_elements:
            if element.get("index") == index:
                return element
        return None

    def find_element_by_bounds(self, bounds: list) -> dict:
        for element in self.view_elements:
            if element.get("bounds") == bounds:
                return element
        return None

    def get_bounds(self, index: int) -> str:
        element = self.find_element_by_index(index)
        if element:
            return element["bounds"]
        return ""

    def _make_description(self) -> str:
        descs = []
        for i, element in enumerate(self.view_elements):
            content = element.get("content", "unknown")
            typ = "Text" if element.get("type") == "text" else "Icon"
            descs.append(f"{typ} Box ID {i}: {content}")
            element["index"] = i  # assign index here
        return "\n".join(descs)

    def _draw_boxes(self, image: Image.Image, elements: list[dict]) -> Image.Image:
        draw = ImageDraw.Draw(image)
        # Fallback font handling (Linux/Windows)
        font_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
        if not os.path.exists(font_path):
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        if not os.path.exists(font_path):
            font_path = "C:\\Windows\\Fonts\\arial.ttf"
        try:
            font = ImageFont.truetype(font_path, 16)
        except OSError:
            font = ImageFont.load_default()
        w, h = image.size

        for i, element in enumerate(elements):
            box = element["bounds"]

            # Normalize handling
            if (
                isinstance(box, (list, tuple))
                and len(box) == 4
                and all(isinstance(v, (int, float)) for v in box)
                and all(0.0 <= float(v) <= 1.0 for v in box)
            ):
                x0 = int(round(box[0] * w))
                y0 = int(round(box[1] * h))
                x1 = int(round(box[2] * w))
                y1 = int(round(box[3] * h))
            else:
                x0 = int(round(box[0]))
                y0 = int(round(box[1]))
                x1 = int(round(box[2]))
                y1 = int(round(box[3]))

            x0, x1 = sorted((x0, x1))
            y0, y1 = sorted((y0, y1))

            x0 = max(0, min(w - 1, x0))
            x1 = max(0, min(w - 1, x1))
            y0 = max(0, min(h - 1, y0))
            y1 = max(0, min(h - 1, y1))

            if x1 <= x0 or y1 <= y0:
                continue

            draw.rectangle([x0, y0, x1, y1], outline="green", width=2)
            draw.text((x0 + 2, y0 + 2), str(i), fill="black", font=font)

        return image

    def _remove_overlap(self, icon_boxes, ocr_boxes):
        """
        OCR 박스를 우선 보존하고, 아이콘 박스와 IoU 0.7 이상 겹치면 제외.
        """
        final_boxes = ocr_boxes.copy()
        for icon in icon_boxes:
            icon_box = icon["bounds"]
            keep = True
            for ocr in ocr_boxes:
                ocr_box = ocr["bounds"]
                if self._iou(icon_box, ocr_box) > 0.7:
                    keep = False
                    break
            if keep:
                final_boxes.append(icon)
        return final_boxes

    def _generate_captions(self, elements, image):
        if isinstance(image, np.ndarray):
            from cv2 import cvtColor, COLOR_BGR2RGB

            image = Image.fromarray(cvtColor(image, COLOR_BGR2RGB))
        elif isinstance(image, Image.Image):
            image = image.convert("RGB")
        else:
            raise TypeError("Expected image to be a PIL.Image or np.ndarray")

        icon_elements = [e for e in elements if e["type"] == "icon"]
        crops = []
        for icon in icon_elements:
            box = [int(x) for x in icon["bounds"]]
            crop = image.crop((box[0], box[1], box[2], box[3])).resize((64, 64)).convert("RGB")
            crops.append(crop)

        if not crops:
            return elements

        inputs = self.processor(
            images=crops,
            text=["<CAPTION>"] * len(crops),
            return_tensors="pt",
            do_resize=False,
        ).to(self.device)

        if self.device.type == "cuda":
            inputs["input_ids"] = inputs["input_ids"].to(torch.long)
            inputs["pixel_values"] = inputs["pixel_values"].to(torch.float16)

        with torch.inference_mode():
            output_ids = self.caption_model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=20,
            )

        captions = self.processor.batch_decode(output_ids, skip_special_tokens=True)
        for icon, caption in zip(icon_elements, captions):
            icon["content"] = caption.strip()
        return elements

    def _iou(self, boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        iou = interArea / float(boxAArea + boxBArea - interArea + 1e-5)
        return iou
