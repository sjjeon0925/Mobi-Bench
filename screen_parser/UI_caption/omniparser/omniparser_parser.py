from screen_parser.base_parser import Parser
from PIL import Image
from typing import Any, Tuple
import torch
import base64
import io
import numpy as np
import os

from screen_parser.omniparser.omni_utils import (
    get_yolo_model,
    get_som_labeled_img,
    check_ocr_box
)

from transformers import AutoProcessor, AutoModelForCausalLM

class OmniParser(Parser):
    def __init__(self):
        super().__init__('omniparser')
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

        som_model_path = os.path.join('screen_parser', 'omniparser', 'icon_detect', 'model.pt')
        caption_model_path = os.path.join('screen_parser', 'omniparser', 'icon_caption')

        # YOLO 모델 가져오기
        self.som_model = get_yolo_model(model_path=som_model_path)
        self.som_model = self.som_model.to(self.device)  # GPU로 올리기

        # 캡션 모델 가져오기
        self.caption_model_processor = {
            'processor': AutoProcessor.from_pretrained(
                "microsoft/Florence-2-base", trust_remote_code=True
            ),
            'model': AutoModelForCausalLM.from_pretrained(
                caption_model_path,
                torch_dtype=torch.float16 if self.device == 'cuda' else torch.float32,
                trust_remote_code=True
            ).to(self.device)
        }

        self.box_threshold = 0.01
        self.iou_threshold = 0.7
        self.filtered_boxes_elem = []
        self.screen_size = (1, 1)

    def parse(self, raw_xml: str) -> str:
        return None  # No XML parsing needed

    def SoM(self, screenshot: Image.Image, raw_xml: str) -> Tuple[Image.Image, str]:
        self.screen_size = screenshot.size
        (ocr_texts, ocr_bboxes), _ = check_ocr_box(
            screenshot,
            display_img=False,
            output_bb_format='xyxy',
            easyocr_args={'text_threshold': 0.8},
            use_paddleocr=False
        )

        labeled_img_b64, _, self.filtered_boxes_elem = get_som_labeled_img(
            image_source=screenshot,
            model=self.som_model,
            BOX_TRESHOLD=self.box_threshold,
            ocr_bbox=ocr_bboxes,
            ocr_text=ocr_texts,
            caption_model_processor=self.caption_model_processor,
            draw_bbox_config={
                'text_scale': 0.8,
                'text_thickness': 2,
                'text_padding': 5,
                'thickness': 3
            },
            use_local_semantics=True,
            iou_threshold=self.iou_threshold,
            scale_img=False
        )

        decoded_img = Image.open(io.BytesIO(base64.b64decode(labeled_img_b64)))

        description_lines = []
        for i, box in enumerate(self.filtered_boxes_elem):
            content = box.get('content')
            if content:
                if box['type'] == 'text':
                    description_lines.append(f"Text Box ID {i}: {content}")
                elif box['type'] == 'icon':
                    description_lines.append(f"Icon Box ID {i}: {content}")

        ui_descriptions = "\n".join(description_lines)

        return decoded_img, ui_descriptions

    def get_pixel_coordinates(self, index: int) -> Tuple[int, int, int, int]:
        if 0 <= index < len(self.filtered_boxes_elem):
            bbox_norm = self.filtered_boxes_elem[index]['bbox']
            w, h = self.screen_size
            x1 = int(bbox_norm[0] * w)
            y1 = int(bbox_norm[1] * h)
            x2 = int(bbox_norm[2] * w)
            y2 = int(bbox_norm[3] * h)
            return (x1, y1, x2, y2)
        return None

    def find_element_by_index(self, index: int) -> Any:
        if 0 <= index < len(self.filtered_boxes_elem):
            return self.filtered_boxes_elem[index]
        return None

    def find_element_by_bounds(self, bounds: str) -> Any:
        try:
            coords = bounds.replace('][', ',').strip('[]').split(',')
            x1, y1, x2, y2 = map(int, coords)
        except:
            return None

        for i, elem in enumerate(self.filtered_boxes_elem):
            px_coords = self.get_pixel_coordinates(i)
            if not px_coords:
                continue
            ex1, ey1, ex2, ey2 = px_coords
            if (ex1 <= x1 and ey1 <= y1 and ex2 >= x2 and ey2 >= y2):
                return elem
        return None

    def get_bounds(self, index: int) -> str:
        coords = self.get_pixel_coordinates(index)
        if coords:
            return f"[{coords[0]},{coords[1]}][{coords[2]},{coords[3]}]"
        return None

    def mark_image(self, image: np.ndarray) -> np.ndarray:
        """
        Mark bounding boxes stored in self.filtered_boxes_elem onto the image.
        """
        if not hasattr(self, "filtered_boxes_elem") or not self.filtered_boxes_elem:
            raise ValueError("filtered_boxes_elem is missing. Call get_som_labeled_img() first.")

        from torchvision.ops import box_convert
        from screen_parser.omniparser.omni_utils import annotate

        if isinstance(image, Image.Image):
            image = np.asarray(image)

        h, w, _ = image.shape

        boxes = torch.tensor([box_elem['bbox'] for box_elem in self.filtered_boxes_elem])
        boxes = box_convert(boxes=boxes, in_fmt="xyxy", out_fmt="cxcywh")

        logits = torch.ones(len(boxes))
        phrases = [str(i) for i in range(len(boxes))]

        annotated_image, _ = annotate(
            image_source=image,
            boxes=boxes,
            logits=logits,
            phrases=phrases,
            text_scale=0.4,
            text_padding=5
        )

        return Image.fromarray(annotated_image)
