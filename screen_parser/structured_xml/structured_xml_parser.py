import xml.etree.ElementTree as ET
import xml.dom.minidom
from PIL import Image, ImageDraw, ImageFont

from screen_parser.base_parser import Parser

class StructuredXmlParser(Parser):
    def __init__(self):
        super().__init__('structured_xml')
        self.bounds_cache = {}

    def _reformat(self,xml_string):
        tree = ET.fromstring(xml_string)

        def process_element(element):
            attrib_text = {
                "text": "text",
                "id": "resource-id",
                "description": "content-desc",
                "important": "important",
                "class": "class"
            }

            attrib_bool = {
                "checkable": "checkable",
                "clickable": "clickable",
                "scrollable": "scrollable",
                "long-clickable": "long-clickable",
            }

            attrib_int = {
                "bounds": "bounds",
                "index": "index",
            }

            new_text_attrib = {
                key: element.attrib[value] for key, value in attrib_text.items() if
                value in element.attrib and element.attrib[value] != ""
            }

            new_bool_attrib = {
                key: element.attrib[value] for key, value in attrib_bool.items() if
                value in element.attrib and element.attrib[value] != "false"
            }

            new_int_attrib = {
                key: element.attrib[value] for key, value in attrib_int.items() if value in element.attrib
            }

            # 0. for "id" attribute, only take what is after "id/"
            if "id" in new_text_attrib:
                new_text_attrib["id"] = new_text_attrib["id"].split("/")[-1]

            # 1. Append new_bool_attrib to new_text_attrib
            new_text_attrib.update(new_bool_attrib)
            new_text_attrib.update(new_int_attrib)

            # 2. make tag name more HTML like.
            class_name = element.attrib.get("class", "unknown")
            class_name_short = class_name.split(".")[-1]  #-2  widget or view

            if class_name_short == "EditText":
                new_element = ET.Element("input", new_text_attrib)
                if len(element) == 0 and "text" in new_element.attrib:
                    text = new_element.attrib.get("text", "")
                    del new_element.attrib["text"]
                    new_element.text = text
            elif new_text_attrib.get("checkable", "") == "true":
                new_text_attrib["checked"] = element.attrib.get("checked", "false")
                del new_text_attrib["checkable"]
                new_element = ET.Element("checker", new_text_attrib)

            elif new_text_attrib.get("clickable", "") == "true":
                del new_text_attrib["clickable"]
                new_element = ET.Element("button", new_text_attrib)

            elif class_name_short in ["FrameLayout", "LinearLayout", "RelativeLayout", "ViewGroup", "ConstraintLayout",
                                    "unknown"]:
                new_element = ET.Element("div", new_text_attrib)

            elif class_name_short == "ImageView":
                new_element = ET.Element("img", new_text_attrib)

            elif class_name_short == "TextView":
                new_element = ET.Element("p", new_text_attrib)
                if len(element) == 0 and "text" in new_element.attrib:
                    text = new_element.attrib.get("text", "")
                    del new_element.attrib["text"]
                    new_element.text = text

            elif new_bool_attrib.get("scrollable", "") == "true":
                new_element = ET.Element("scroll", new_text_attrib)
            else:
                new_element = ET.Element(class_name.split(".")[-1], new_text_attrib)

            for child in element:
                new_child = process_element(child)

                if new_child is not None:
                    new_element.append(new_child)

            # skip leaf node that is meaningless e.g., no text or description attribute
            if new_element.tag not in ['button', 'checker'] and len(element) == 0 and 'description' not in new_element.attrib and not new_element.text:
                return None

            return new_element

        new_tree = process_element(tree)
        return ET.tostring(new_tree, encoding='unicode')


    def _simplify(self,xml_string):
        tree = ET.ElementTree(ET.fromstring(xml_string))
        root = tree.getroot()

        # Recursive function to simplify the XML by removing unnecessary wrappers
        def simplify_element(elem):
            # While the current element has only one child, replace it with its child
            while len(list(elem)) == 1 and all(x not in elem.attrib for x in ['text', 'description']):
                if elem.tag in ['button', 'checker']:
                    break
                child = elem[0]
                elem.tag = child.tag
                elem.attrib = child.attrib
                elem.text = child.text
                elem[:] = child[:]  # Replace elem's children with child's children

            # Continue to check for each child of the current element
            for subelem in list(elem):
                simplify_element(subelem)

        # Start the simplification from the root
        simplify_element(root)

        return ET.tostring(root, encoding='unicode')

    def _remove_nodes_with_empty_bounds(self,element):
        for node in list(element):
            if node.get('bounds') == "[0,0][0,0]":
                element.remove(node)
            else:
                self._remove_nodes_with_empty_bounds(node)

    def _clean(self, xml_string):
        root = ET.fromstring(xml_string)
        self._remove_nodes_with_empty_bounds(root)

        # remove bounds attribute, which is unnecessary for gpt.
        for element in root.iter():
            # if 'bounds' in element.attrib:
            #     del element.attrib['bounds']
            if 'important' in element.attrib:
                del element.attrib['important']
            if 'class' in element.attrib:
                del element.attrib['class']

        return ET.tostring(root, encoding='unicode')
        

    def _renumber(self, xml_string):
        """
        Reassigns sequential index numbers to all elements in the XML tree.
        
        Args:
            xml_string: The XML string to process
            
        Returns:
            The XML string with renumbered indices
        """
        root = ET.fromstring(xml_string)
        current_index = 0
        
        # Traverse the tree in pre-order and assign new indices
        for element in root.iter():
            element.attrib['index'] = str(current_index)
            current_index += 1
        
        return ET.tostring(root, encoding='unicode')
    
    def _add_mark(self, screenshot: Image.Image, bounds_str: str, index: str):
        """
        Parse the 'bounds' attribute, draw bounding box & index on screenshot.
        """
        # Typical format of bounds_str is "[left,top][right,bottom]" 
        # e.g., "[0,12][144,98]"
        try:
            coords = bounds_str.replace('][', ',').strip('[]').split(',')
            left, top, right, bottom = list(map(int, coords))
        except:
            return  # If parsing fails, just skip

        draw = ImageDraw.Draw(screenshot)
        
        # Draw bounding rectangle in green
        draw.rectangle([(left, top), (right, bottom)], outline=(0, 255, 0), width=2)

        # Add a small rectangle to hold the text index
        text_bg_size = (35, 25)
        draw.rectangle(
            [(left, top), (left + text_bg_size[0], top + text_bg_size[1])],
            fill=(255, 255, 255)  # White background
        )
        
        # Try a bold font, else fallback
        # Change font size
        font = ImageFont.load_default().font_variant(size=20)  

        # Put index in the corner box
        draw.text((left + 1, top + 1), index, fill=(0, 0, 0), font=font)

    def _clear_bounds(self, xml_string):
        # Clear existing bounds cache
        self.bounds_cache.clear()


        root = ET.fromstring(xml_string)
        # Iterate through all elements
        for element in root.iter():
            # Get bounds and index if they exist
            bounds = element.get('bounds')
            index = element.get('index')
            
            # If both bounds and index exist, cache the bounds and remove from element
            if bounds and index:
                self.bounds_cache[index] = bounds
                element.attrib.pop('bounds')

        # Convert back to string
        return ET.tostring(root, encoding='unicode')
    
    def parse(self, raw_xml)->str:
        # Reformat the XML to make it more readable
        reformatted_xml = self._reformat(raw_xml)

        # Remove unncessary wrapper UIs (UI with only one childe)
        simplified_xml = self._simplify(reformatted_xml)
        
        # Remove empty UI and aux attributes
        cleaned_xml = self._clean(simplified_xml)
        
        # Renumber all elements
        renumbered_xml = self._renumber(cleaned_xml)
        
        # Clear bounds attribute
        bounds_cleared_xml = self._clear_bounds(renumbered_xml)

        return bounds_cleared_xml
    
    def SoM(self, screenshot: Image.Image, raw_xml: str):
        """
        1) Load screenshot.
        2) Parse raw XML to produce simplified HTML-like structure.
        3) Draw bounding boxes from the final parsed structure.
        4) Save annotated screenshot and return with final HTML string.
        """

        # 2. Parse raw XML -> final simplified HTML string
        final_xml_str = self.parse(raw_xml)

        # 3. Draw bounding boxes (if 'bounds' is present) on the screenshot
        root = ET.fromstring(final_xml_str)
        for element in root.iter():
            bounds = self.bounds_cache.get(element.get('index'))
            index = element.get('index')
            if bounds and index:
                self._add_mark(screenshot, bounds, index)

        # 4. Return the screenshot and the final simplified HTML string
        return screenshot, final_xml_str

    def find_element_by_index(self, index: int, xml_string: str) -> ET.Element:
        """
        Find UI element in XML tree by its index attribute.
        
        Args:
            index: The index value to search for
            
        Returns:
            Element if found, None otherwise
        """
        if xml_string is None:
            return None
        
        # Parse the XML string into an ElementTree
        root = ET.fromstring(xml_string)
        tree = ET.ElementTree(root)
        
        for element in tree.iter():
            if element.get('index') == str(index):
                return element
        return None
    
    def find_element_by_bounds(self, bounds: str, xml_string: str) -> ET.Element:
        """
        Find UI element by bounds using the same strategy as UI_element parser:
        1) Prefer exact bounds match.
        2) If not found, return the smallest-area element whose bounds fully contain the target bounds.

        Args:
            bounds: Target bounds string (e.g., "[x1,y1][x2,y2]")
            xml_string: XML to search in

        Returns:
            Element if found, else None
        """
        if xml_string is None or bounds is None:
            return None

        # Parse XML
        root = ET.fromstring(xml_string)
        tree = ET.ElementTree(root)

        # 1) Exact match first
        for element in tree.iter():
            idx = element.get('index')
            if idx is not None and self.bounds_cache.get(idx) == bounds:
                return element

        # 2) Containment + min area
        try:
            target = bounds.replace('][', ',').strip('[]').split(',')
            tx1, ty1, tx2, ty2 = map(int, target)
        except Exception:
            return None

        candidates = []
        for element in tree.iter():
            idx = element.get('index')
            b = self.bounds_cache.get(idx) if idx is not None else None
            if not b:
                continue
            try:
                coords = b.replace('][', ',').strip('[]').split(',')
                x1, y1, x2, y2 = map(int, coords)
            except Exception:
                continue
            # Check containment: element fully contains target
            if x1 <= tx1 and y1 <= ty1 and x2 >= tx2 and y2 >= ty2:
                candidates.append((element, b))

        if not candidates:
            return None

        # Return element with smallest area among candidates
        element_min, _ = min(candidates, key=lambda pair: _get_area(pair[1]))
        return element_min
    
    def get_bounds(self, element: ET.Element) -> str:
        return self.bounds_cache.get(element.get('index'))
    
    def find_element_by_point(self, point: tuple[int, int], xml_string: str) -> ET.Element:
        if xml_string is None:
            return None
            
        root = ET.fromstring(xml_string)
        tree = ET.ElementTree(root)
        matching_elements = []
        
        # Find all elements that contain the point
        for element in tree.iter():
            bounds = self.bounds_cache.get(element.get('index'))
            if bounds:
                # Parse bounds string "[x1,y1][x2,y2]" into coordinates
                try:
                    coords = bounds.replace('][', ',').strip('[]').split(',')
                    x1, y1, x2, y2 = map(int, coords)
                    
                    # Check if point is within bounds
                    if x1 <= point[0] <= x2 and y1 <= point[1] <= y2:
                        matching_elements.append(element)
                except:
                    continue
                    
        if not matching_elements:
            return None
            
        # Return element with smallest area
        return min(matching_elements, 
                  key=lambda e: _get_area(self.bounds_cache.get(e.get('index'))))
                  
def _get_area(bounds: str) -> int:
    """Helper to calculate area of element bounds"""
    if not bounds:
        return float('inf')
    coords = bounds.replace('][', ',').strip('[]').split(',')
    x1, y1, x2, y2 = map(int, coords)
    return (x2 - x1) * (y2 - y1)