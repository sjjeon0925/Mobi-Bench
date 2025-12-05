import os
import re

from utils import log, generate_numbered_list

from PIL import Image, ImageDraw, ImageFont
import xml.etree.ElementTree as ET
from screen_parser.structured_xml.structured_xml_parser import StructuredXmlParser
from model.base_model import GPTWrapper
import json
import time


class PreActionReflectionAgent:
    def __init__(self, save_path: str, parser=None, reflection_model=None):
        if reflection_model is not None:
            self.GPT = reflection_model
        else:
            # 기본값으로 gpt-4o-mini 사용 (하위 호환성)
            self.GPT = GPTWrapper("gpt-4o-mini", temperature=0.0)
        self.parser = parser if parser else StructuredXmlParser()
        self.save_path = save_path
        self.step_count = 0
        self.name = "Pre_action_reflection_agent"

    def reset(self, app_name: str, instruction: str):
        self.app_name = app_name
        self.instruction = instruction
        self.history = []
    
    def save_highlighted_element(self, image, action):
        """Disabled: do not save highlighted images to disk."""
        log("Skipping highlighted image save (disabled).", "yellow")
        return None

    def pre_action_reflection(self, result_path: str, action: dict, som_screenshot, parsed_xml: str, history, is_input_check: bool = False):
        #som_screenshot, parsed_xml = self.parser.SoM(screenshot, xml)

        listed_history = []
        for i, step_info in enumerate(history[:-1]):
            summary = step_info.get("summary", "")
            # Flatten list summaries
            if isinstance(summary, list):
                summary = " ".join(str(s) for s in summary if s)
            # Skip boilerplate "open the app" entry
            if i == 0 and isinstance(summary, str) and summary.strip().lower() == "open the app":
                continue
            listed_history.append(f"Step {len(listed_history) + 1}: {summary}")

        if action.get("action_type") != "navigate_back" and action.get("action_type") != "finish" and action.get("action_type") != "scroll" and action.get("bounds") != None:
            #action['index'] = self.parser.find_element_by_bounds(action["bounds"]).get('index')
            # Highlight saving disabled
            path = None

            action.pop("bounds")
        else:
            tmp_saving_som_path = self.save_path + "/tmp_som.png"
            os.makedirs(os.path.dirname(tmp_saving_som_path), exist_ok=True)
            som_screenshot.save(tmp_saving_som_path)
            path = tmp_saving_som_path
        
        if "default" in action.keys():
            action.pop("default")

        if "params" in action.keys():
            if not isinstance(action["params"], dict):
                action["params"] = {}
            if "text" in action["params"].keys():
                action["text"] = action["params"]["text"]
                action.pop("params")
            elif "direction" in action["params"].keys():
                action["direction"] = action["params"]["direction"]
                action.pop("params")
        
        system_prompt = VERIFICATION_ACTION_PROMPT_TEMPLATE_MM_SINGLE_SCREEN.format(
            goal=self.instruction,
            app_name=self.app_name,
            history=listed_history,
            before_elements=parsed_xml,
            action=action
        )

        if is_input_check:
            # Input check mode: return input validation info without GPT call
            input_info = {
                "system_prompt": system_prompt,
                "image_path": path,
                "parsed_xml": parsed_xml,
                "processed_action": action,
                "history": self.history
            }
            print("=== PRE-ACTION REFLECTION INPUT CHECK ===")
            print(f"System Prompt Length: {len(system_prompt)}")
            print(f"Image Path: {path}")
            print(f"Parsed XML Length: {len(parsed_xml)}")
            print(f"Processed Action: {action}")
            print(f"History Length: {len(self.history)}")
            print("=========================================")
            return True, "Input check completed", input_info

        # GPT 호출 및 히스토리 업데이트
        retry = 0
        start_index = -1
        end_index = -1
        # Only one attempt unless the format is totally unusable
        max_retry = 1
        while retry < max_retry:
            try:
                raw_result, response_generation = self.GPT.query_mm(system_prompt, som_screenshot)
                if raw_result:
                    start_index = raw_result.find('{')
                    end_index = raw_result.rfind('}')
                    if start_index == -1 or end_index == -1:
                        log(f"Invalid JSON format in response (retry {retry+1})", 'red')
                        retry += 1
                        continue
                    break
                else:
                    log(f"No response from GPT (retry {retry+1})", 'red')
                    retry += 1
            except Exception as e:
                log(f"GPT query failed (retry {retry+1}): {e}", 'red')
                retry += 1
                if retry >= max_retry:
                    log("All retries failed. Returning empty response.", 'red')
                    return False, "No response from GPT", {}

        # simplified: no reflection model call timing log

        if start_index != -1 and end_index != -1:
            json_part = raw_result[start_index:end_index+1]
            try:
                result = json.loads(json_part)
            except Exception as e:
                log(f"JSON decode failed in reflection: {e}", "red")
                return False, "No valid JSON in reflection", {}
        else:
            return False, "No valid JSON in reflection", {}

        with open(os.path.join(result_path, "response.txt"), 'a') as f:
                f.write(json.dumps({
                    "type": "reflection",
                    "app_name": self.app_name,
                    "instruction": self.instruction,
                    "correct": result.get("correct", False),
                    "feedback": result.get("feedback", ""),
                    "explanation": result.get("explanation", ""),
                    "generation": response_generation if 'response_generation' in locals() else None
                }) + ',\n')

        print(result)
        # If the action is judged incorrect, explicitly forbid repeating it
        if not result.get("correct", False):
            avoid_text = json.dumps(action, ensure_ascii=False)
            extra_note = f" Do NOT repeat this action: {avoid_text}"
            if result.get("feedback"):
                result["feedback"] = str(result["feedback"]) + extra_note
            else:
                result["feedback"] = extra_note
        return result["correct"], result["feedback"], result
    
    def action_history_checking(self):    
        system_prompt = HISTORY_VERIFICATION_PROMPT_TEMPLATE.format(
            goal=self.instruction,
            app_name=self.app_name,
            action_history=generate_numbered_list(self.history)
        )
        result = self.GPT.text_query(system_prompt, "")
        return result["answer"]["correct"], result["answer"]["feedback"], result
    
PROMPT_PREFIX_VERIFICATION = (
    'You are an agent capable of operating an Android phone on behalf of a user.\n\n'
    'The current step is to verify the action you performed. Based on the resources provided, determine whether the action you decided to take to achieve your GOAL was correct. The process of how you decided on this action will be explained to you.:\n\n'
    'Tasks described in the request/goal are executed step by step, progressing through actions on the phone. When a user request is given, you attempt to complete the task step by step. At each step, a list of descriptions for most UI elements on the current screen will be provided (each element can be specified by an index). Additionally, the history of actions you previously performed will also be provided. Based on this information and the goal, you must select one of the tasks from the following list (including action descriptions and JSON format) and output the selected task in the correct JSON format.\n\n'
)

ACTION_EXAMPLE_LIST_PREFIX = (
    """
action example list:
- Click/tap on a UI element (specified by its index) on the screen:
 `{{"action_type": "click", "index": <target_UI_index>}}`.
  Use only when the element is already visible and unambiguous. The click should immediately trigger the next UI change (open a page, toggle a control, confirm a dialog). Do not click blindly, identify the correct index from the UI descriptions and Do not forget to cite that index in the JSON.

- Type text:
 `{{"action_type": "input", "index": <target_UI_index>, "params": {{"text": "<text_input>"}}}}`.
Use only when the goal explicitly requires entering text into the focused field (search, login, chat input). Do not combine with manual clicks on the keyboard; describe the exact text you will enter and always wrap it in `params.text`. Do not forget to include the correct index as well.

- Scroll the current screen or list:
 `{{"action_type": "scroll", "direction": <up, down, left, right>}}`.
  Use when the element you need is off-screen or more content needs to be revealed. Choose the direction that moves toward the target (e.g., `down` to reveal lower content). Do not over-scroll; perform one scroll per action.

- Navigate back:
 `{{"action_type": "navigate_back"}}`.
  Use when the current screen is a dead end, you opened the wrong page, or the goal requires returning to the previous view. Do not use `click` on on-screen back buttons unless the instruction explicitly calls for that specific UI button.

- Open an app (if installed):
 `{{"action_type": "open_app", "params": {{"app": <app_name>}}}}`.
  Use at the start of a task or whenever you must switch apps. Do not scroll the home screen or tap icons manually to find an app. Always issue `open_app` with the app name and let the system launch it. If the app name is given in the goal, copy it exactly.

- Finish the task:
 `{{"action_type": "finish", "status": "complete"}}`.
  Only use after verifying that every requirement in the goal has been satisfied. Once the task is complete, choose `finish` immediately instead of taking additional exploratory actions.
"""
)

VERIFICATION_ACTION_PROMPT_TEMPLATE_MM_SINGLE_SCREEN = (
    PROMPT_PREFIX_VERIFICATION + ACTION_EXAMPLE_LIST_PREFIX
    + '\nThe (overall) user goal/request is: {goal} / App name: {app_name}\n'
    'Here is a history of what you have done so far:\n0. open the app\n{history}\n\n'
    'Now I want you to verify whether the next chosen action is correct.\n'
    'Here is the HTML representation (description) of the screen before the action (related with the screenshot image):'
    '\n{before_elements}\n\n'
    'On this screen you choose the following actionscreen: {action}\n\n'
    'Your task is to determine if the action is correct given the'
    ' screen before the action. Be extremely strict: if any part of the action looks wrong, risky, or even slightly misaligned (wrong index/bounds/coordinates/text/direction/app), mark it incorrect. The action is correct only if it clearly moves one step closer to the goal.\n'
    'Respond with the result in JSON format.\n'
    '- Include "correct" (boolean) indicating if the action is correct.\n'
    '- Include "explanation" (string) explaining the reasoning.\n'
    '- If the action is incorrect, include "feedback" (string) providing feedback on what went wrong and how to fix it if applicable, or "none" if no fixes are needed.\n\n'
    'You must respond in json format:\n'
    '{{\n'
    '  "index_interpretation": "<Your interpretation of the target index UI element.>",\n'
    '  "predication_action_result": "<Your prediction of the action result.>",\n'
    '  "action_interpretation": "<short description of the action. do not include the specific index and prediction result. Don\'t start \'the user\' start. start with nominalization.>",\n'
    '  "explanation": "<Your explanation about correct or incorrect.>",\n'
    '  "correct": true or false,\n'
    '  "feedback": "<Explanation of how to fix the issue or none if no fixes are needed.>"\n'
    '}}\n\n'
    'Verification result: '
)

PROMPT_PREFIX_HISTORY_VERIFICATION = (
    'You are an agent capable of operating an Android phone on behalf of a user.\n\n'
    'The current step is to verify the action history you performed. Based on the resources provided, determine whether the action history you decided to take to achieve your GOAL was correct. The process of how you decided on this action will be explained to you.:\n\n'
    'Tasks described in the request/goal are executed step by step, progressing through actions on the phone. When a user request is given, you attempt to complete the task step by step. At each step, a list of descriptions for most UI elements on the current screen will be provided (each element can be specified by an index). Additionally, the history of actions you previously performed will also be provided. Based on this information and the goal, you must select one of the tasks from the following list (including action descriptions and JSON format) and output the selected task in the correct JSON format.\n\n'
)

HISTORY_VERIFICATION_PROMPT_TEMPLATE = (
    PROMPT_PREFIX_HISTORY_VERIFICATION + ACTION_EXAMPLE_LIST_PREFIX
    + '\nThe (overall) user goal/request is: {goal} / App name: {app_name}\n'
    'You will be provided with a list of action summaries that represent the'
    ' steps taken so far toward completing the task.\n\n'
    'Here is the list of action summaries (in chronological order):\n'
    '0. open the app\n{action_history}\n\n'
    'Your task is to verify whether the current path is correct and aligned with achieving the goal.\n'
    'If the path is incorrect, provide feedback on what went wrong and how to correct it.\n\n'
    'Respond in JSON format with the following fields:\n'
    '- "correct" (boolean) indicating if the sequence of actions taken so far is correct.\n'
    '- "explanation" (string) summarizing why the path is or is not correct.\n'
    '- "feedback" (string) providing feedback on what went wrong and how to fix it if applicable, or "none" if no fixes are needed.\n\n'
    '!!You must respond in json format!!:\n'
    '{{\n'
    '  "explanation": "<Your explanation here.>",\n'
    '  "correct": true or false,\n'
    '  "feedback": "<Explanation of how to fix the issue or none if no fixes are needed.>"\n'
    '}}\n\n'
    'Verification result: '
)
