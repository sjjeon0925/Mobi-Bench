import os
from screen_parser.structured_xml.structured_xml_parser import parse
import xml.dom.minidom

# Dump and pull the UI XML file
os.system("adb shell uiautomator dump /sdcard/window_dump.xml && adb pull /sdcard/window_dump.xml ./window_dump.xml")

# Read the dumped XML file
with open("window_dump.xml", "r", encoding="utf-8") as f:
    raw_xml = f.read()

# Parse the XML using the parser functions
parsed_xml = parse(raw_xml)

# Create a pretty-printed version
dom = xml.dom.minidom.parseString(parsed_xml)
pretty_xml = dom.toprettyxml(indent="  ")

# Save the pretty-printed XML to a file
with open("pretty.xml", "w", encoding="utf-8") as f:
    f.write(pretty_xml)
