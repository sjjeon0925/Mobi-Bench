import dataclasses
import json
from screen_parser.base_parser import Parser
import xml.etree.ElementTree as ET
from typing import Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

@dataclasses.dataclass
class BoundingBox:
  """Class for representing a bounding box."""

  x_min: float | int
  x_max: float | int
  y_min: float | int
  y_max: float | int

  @property
  def center(self) -> tuple[float, float]:
    """Gets center of bounding box."""
    return (self.x_min + self.x_max) / 2.0, (self.y_min + self.y_max) / 2.0

  @property
  def width(self) -> float | int:
    """Gets width of bounding box."""
    return self.x_max - self.x_min

  @property
  def height(self) -> float | int:
    """Gets height of bounding box."""
    return self.y_max - self.y_min

  @property
  def area(self) -> float | int:
    return self.width * self.height
  
@dataclasses.dataclass
class UIElement:
  """Represents a UI element."""

  index: int
  text: Optional[str] = None
  content_description: Optional[str] = None
  class_name: Optional[str] = None
  bounds: Optional[str] = None
  bbox_pixels: Optional[BoundingBox] = None
  bbox_normalized: Optional[BoundingBox] = None
  hint_text: Optional[str] = None
  is_checked: Optional[bool] = None
  is_checkable: Optional[bool] = None
  is_clickable: Optional[bool] = None
  is_editable: Optional[bool] = None
  is_enabled: Optional[bool] = None
  is_focused: Optional[bool] = None
  is_focusable: Optional[bool] = None
  is_long_clickable: Optional[bool] = None
  is_scrollable: Optional[bool] = None
  is_selected: Optional[bool] = None
  is_visible: Optional[bool] = None
  package_name: Optional[str] = None
  resource_name: Optional[str] = None
  tooltip: Optional[str] = None
  resource_id: Optional[str] = None

  def get(self, attribute: str) -> Any:
    """Gets the value of the specified attribute.
    
    Args:
        attribute: Name of the attribute to retrieve
        
    Returns:
        The value of the attribute if it exists, None otherwise
    """
    return getattr(self, attribute, None)

def _normalize_bounding_box(
    node_bbox: BoundingBox,
    screen_width_height_px: tuple[int, int],
) -> BoundingBox:
  width, height = screen_width_height_px
  return BoundingBox(
      node_bbox.x_min / width,
      node_bbox.x_max / width,
      node_bbox.y_min / height,
      node_bbox.y_max / height,
  )

def accessibility_node_to_ui_element(
    node: ET.Element,
    index: int,
    screen_size: Optional[tuple[int, int]] = None,

) -> UIElement:
    """Converts a node from an accessibility tree to a UIElement."""

    def text_or_none(text: Optional[str]) -> Optional[str]:
        """Returns None if text is None or 0 length."""
        return text if text else None

    # Parse bounds string into BoundingBox
    bounds_str = node.get('bounds')
    if bounds_str:
        # Bounds format is typically "[left,top][right,bottom]"
        bounds = bounds_str.replace('][', ',').strip('[]').split(',')
        bbox_pixels = BoundingBox(
            int(bounds[0]), int(bounds[2]),  # x_min, x_max
            int(bounds[1]), int(bounds[3])   # y_min, y_max
        )
        if screen_size is not None and bbox_pixels is not None:
            bbox_normalized = _normalize_bounding_box(bbox_pixels, screen_size)
        else:
            bbox_normalized = BoundingBox(0, 0, 0, 0)
    else:
        bbox_pixels = BoundingBox(0, 0, 0, 0)
        bbox_normalized = BoundingBox(0, 0, 0, 0)

    def bool_true(attribute: str) -> Optional[bool]:
        return True if node.get(attribute) == 'true' else None

    return UIElement(
        index=index,
        text=text_or_none(node.get('text')),
        content_description=text_or_none(node.get('content-desc')),
        class_name=text_or_none(node.get('class')),
        bounds=node.get('bounds'),
        bbox_pixels=bbox_pixels,
        bbox_normalized=bbox_normalized,
        hint_text=text_or_none(node.get('hint')),
        is_checked=bool_true('checked'),
        is_checkable=bool_true('checkable'),
        is_clickable=bool_true('clickable'),
        is_editable=bool_true('editable'),
        is_enabled=bool_true('enabled'),
        is_focused=bool_true('focused'),
        is_focusable=bool_true('focusable'),
        is_long_clickable=bool_true('long-clickable'),
        is_scrollable=bool_true('scrollable'),
        is_selected=bool_true('selected'),
        package_name=text_or_none(node.get('package')),
        resource_name=text_or_none(node.get('resource-id')),
    )

class UIElementParser(Parser):
    def __init__(self):
        super().__init__('UI_element')
        self.views = []
        self.name = 'UI_element'

    def tree_to_ui_elements(self, tree: ET.Element) -> list[UIElement]:
        """Select UI elements using the same include/exclude rule as StructuredXmlParser,
        while keeping the UI_element flat-list output format.

        Inclusion rule mirrored from structured_xml:
        - Drop any node (and its subtree) whose bounds are exactly "[0,0][0,0]".
        - Always include nodes with clickable==true or checkable==true (button/checker in structured_xml),
          regardless of being leaf or having text/description.
        - Otherwise include only leaf nodes (no children) that have either non-empty text or non-empty content-desc.
        - Nodes that are only scrollable without text/description are NOT included (structured_xml would drop
          such meaningless leaves and doesn't special-case scroll for leaf-keep).
        - Additionally, exclude any included node with zero area bounds, to match previous behavior.
        """

        elements: list[UIElement] = []
        count = 0

        def walk(node: ET.Element, ancestor_pruned: bool = False):
            nonlocal count

            # If an ancestor was pruned due to empty bounds, skip entire subtree
            if ancestor_pruned:
                return

            # Current node bounds pruning (structured_xml removes nodes with empty bounds)
            bounds_str = node.get('bounds')
            current_pruned = (bounds_str == "[0,0][0,0]")
            if current_pruned:
                return  # do not visit children either

            # Determine inclusion according to structured_xml rules
            clickable = node.get('clickable') == 'true'
            checkable = node.get('checkable') == 'true'
            is_leaf = (len(node) == 0)
            text_val = (node.get('text') or "").strip()
            desc_val = (node.get('content-desc') or "").strip()

            include = False
            if clickable or checkable:
                include = True
            elif is_leaf and (text_val != "" or desc_val != ""):
                include = True

            if include:
                ui_element = accessibility_node_to_ui_element(node, count)
                # Keep only elements with positive area
                if ui_element.bbox_pixels and ui_element.bbox_pixels.area > 0:
                    elements.append(ui_element)
                    count += 1

            # Recurse into children
            for child in list(node):
                walk(child, ancestor_pruned=False)

        walk(tree, ancestor_pruned=False)
        return elements

    def generate_ui_elements_descriptions(self, ui_elements: list[UIElement]) -> str:
        """Generate M3A-style description for a list of UIElement."""
        descriptions = ''
        for index, ui_element in enumerate(ui_elements):
            parts = [f'"index": {index}']

            if ui_element.text:
                parts.append(f'"text": "{ui_element.text}"')
            if ui_element.content_description:
                parts.append(f'"content_description": "{ui_element.content_description}"')
            if ui_element.hint_text:
                parts.append(f'"hint_text": "{ui_element.hint_text}"')
            if ui_element.tooltip:
                parts.append(f'"tooltip": "{ui_element.tooltip}"')

            if ui_element.bounds:
                parts.append(f'"bounds": "{ui_element.bounds}"')

            bool_fields = [
                ("is_clickable", ui_element.is_clickable),
                ("is_long_clickable", ui_element.is_long_clickable),
                ("is_editable", ui_element.is_editable),
                ("is_scrollable", ui_element.is_scrollable),
                ("is_focusable", ui_element.is_focusable),
                ("is_selected", ui_element.is_selected),
                ("is_checked", ui_element.is_checked),
                ("is_checkable", ui_element.is_checkable),
                ("is_enabled", ui_element.is_enabled),
                ("is_focused", ui_element.is_focused),
            ]
            for label, value in bool_fields:
                if value:
                    parts.append(f'"{label}": "True"')

            inner_desc = ", ".join(parts)
            descriptions += f'UI element {index}: {{{inner_desc}}}\n'
        return descriptions
    def _add_mark(self, screenshot: Image.Image, ui_element: UIElement):
        """Add mark (a bounding box plus index) for a UI element in the screenshot.
        
        Args:
            screenshot: The PIL Image screenshot
            ui_element: The UI element to be marked
            index: The index for the UI element
        """
        if ui_element.bbox_pixels:
            # Create ImageDraw object for drawing on the image
            draw = ImageDraw.Draw(screenshot)
            
            # Get coordinates for rectangle
            upper_left = (ui_element.bbox_pixels.x_min, ui_element.bbox_pixels.y_min)
            lower_right = (ui_element.bbox_pixels.x_max, ui_element.bbox_pixels.y_max)
            # Draw green rectangle
            draw.rectangle(
                [upper_left, lower_right],
                outline=(0, 255, 0),  # Green color
                width=2
            )
            
            # Create white background for text
            text_bg_size = (35, 25)
            draw.rectangle(
                [
                    upper_left,
                    (upper_left[0] + text_bg_size[0], upper_left[1] + text_bg_size[1])
                ],
                fill=(255, 255, 255)  # White background
            )
            
            # Add index number
            # Change font size
            font = ImageFont.load_default().font_variant(size=20)  
                
            draw.text(
                (upper_left[0] + 1, upper_left[1] + 1),
                str(ui_element.index),
                fill=(0, 0, 0),  # Black text
                font=font
            )
    def parse(self, raw_xml: str)->str:
        tree = ET.fromstring(raw_xml)
        self.views = self.tree_to_ui_elements(tree)
        ui_descriptions = self.generate_ui_elements_descriptions(self.views)
        return ui_descriptions
    
    def SoM(self, screenshot: Image.Image, raw_xml: str) -> Tuple[Image.Image, str]:
        tree = ET.fromstring(raw_xml)
        self.views = self.tree_to_ui_elements(tree)
        for ui_element in self.views:
            self._add_mark(screenshot, ui_element)
        ui_descriptions = self.generate_ui_elements_descriptions(self.views)
        return screenshot, ui_descriptions

    def find_element_by_index(self, index: int) -> UIElement:
        for element in self.views:
            if element.index == index:
                return element
        return None
    
    def find_element_by_point(self, point: tuple[int, int]) -> UIElement:
        matching_elements = []
        
        # Find all elements that contain the point
        for element in self.views:
            if element.bbox_pixels and element.bbox_pixels.x_min <= point[0] and element.bbox_pixels.x_max >= point[0] and element.bbox_pixels.y_min <= point[1] and element.bbox_pixels.y_max >= point[1]:
                matching_elements.append(element)
                
        if not matching_elements:
            return None
            
        # Find element with smallest bounds area
        return min(matching_elements, key=lambda e: e.bbox_pixels.area)

    def find_element_by_bounds(self, bounds: str) -> UIElement:
        """
        Find the smallest UI element that contains the given bounds.
        
        Args:
            bounds: The bounds value to search for
            xml_string: The XML string to search in
            
        Returns:
            Element if found, None otherwise
        """
        if self.views is None or bounds is None:
            return None
            
        # Parse bounds into coordinates
        try:
            target_coords = bounds.replace('][', ',').strip('[]').split(',')
            tx1, ty1, tx2, ty2 = map(int, target_coords)
        except:
            return None
            
        # Find all elements that contain the target bounds
        matching_elements = []
        
        for element in self.views:
            element_bounds = element.bounds

            if element_bounds == bounds:
                return element
            
            try:
                coords = element_bounds.replace('][', ',').strip('[]').split(',')
                x1, y1, x2, y2 = map(int, coords)
                
                # Check if this element fully contains the target bounds
                if x1 <= tx1 and y1 <= ty1 and x2 >= tx2 and y2 >= ty2:
                    matching_elements.append(element)
            except:
                continue
        
        if not matching_elements:
            return None
            
        # Return element with smallest area
        return min(matching_elements, 
                  key=lambda e: e.bbox_pixels.area)
        
    
    def get_bounds(self, index: int) -> str:
        for element in self.views:
            if element.index == index:
                return element.bounds
        return None
    
    def get_middle_point(self, bounds: list[int]) -> tuple[int, int]:

        # 경계 값을 각 변수에 할당 (e.g., x1=100, y1=200, x2=300, y2=400)
        x1, y1, x2, y2 = bounds
        
        # 중간 지점의 x, y 좌표를 계산 (정수 좌표를 위해 // 연산자 사용)
        middle_x = (x1 + x2) // 2
        middle_y = (y1 + y2) // 2
        
        # (x, y) 튜플 형태로 중간 지점 좌표를 반환
        return (middle_x, middle_y)
