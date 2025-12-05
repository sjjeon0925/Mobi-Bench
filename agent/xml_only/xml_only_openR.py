import json
import time
from agent import base_agent
from agent.base_agent import Agent, AgentInteractionData

from environment.base_env import Env, EnvInteractionResult
from model.base_model import Model
from utils import parse_json
import os
from datetime import datetime
from reflection_agent.pre_action_reflection import PreActionReflectionAgent

class XmlOnlyAgent(Agent):
    def __init__(self, model: Model, reflection_model: Model, summary_model: Model, env: Env, prompt, summary_type: str = "post", prompt_type: str = "react", reflection_type: str = "no_reflection", som_mode: str = "som", save_screenshots: bool = True):
        super().__init__(model, env, 'xmlonly')

        self.name = 'xml_only'
        self.history = []
        self.additional_guidelines = []
        self.prompts = prompt
        self.summary = None
        self.reflection_type = reflection_type
        self.reflection = None
        self.summary_type = summary_type
        self.prompt_type = prompt_type
        self.summary_model = summary_model
        self.reflection_model = reflection_model
        self.env = env
        print("prompt_type", self.prompt_type)
        self.som_mode = som_mode  # "som" or "nosom"
        self.results_path = None
        os.makedirs(os.path.join("./results", self.name), exist_ok=True)
        self.env.results_path = os.path.join("./results", self.name, f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{self.env.parser.name}_{self.som_mode}_summary_{self.summary_type}_model_{self.model.name.replace('/', '-')}_prompt_{self.prompt_type}_reflect_{self.reflection_type}")
        os.makedirs(self.env.results_path, exist_ok=True)
        self.raw_log_file = os.path.join(self.env.results_path, "raw_model_outputs.log")
        self.save_screenshots = save_screenshots
        self._screenshot_dir = None
        if self.save_screenshots:
            self._screenshot_dir = os.path.join(self.env.results_path, "screenshots")
            os.makedirs(self._screenshot_dir, exist_ok=True)
        self._screenshot_counter = 0

        if self.reflection_type == "pre" and self.reflection_model is not None:
            self.reflection_agent = PreActionReflectionAgent(self.env.results_path, self.env.parser, self.reflection_model)
        else:
            self.reflection_agent = None

    def _get_screen(self):
        if self.som_mode == "som":
            return self.env.get_screenshot_with_som()
        else:
            return self.env.get_screenshot_without_som()

    def reset(self, instruction: str):
        super().reset(instruction)
        # Clear only image data from history, keep text for prompt generation
        for step_data in self.history:
            if 'before_screenshot' in step_data:
                step_data['before_screenshot'] = None
            if 'after_screenshot' in step_data:
                step_data['after_screenshot'] = None
            if 'before_raw_screenshot' in step_data:
                step_data['before_raw_screenshot'] = None
            if 'after_raw_screenshot' in step_data:
                step_data['after_raw_screenshot'] = None
        # Then clear the list for new task
        self.history.clear()
        
    def __del__(self):
        """Cleanup method to free memory when agent is destroyed."""
        if hasattr(self, 'history'):
            # Clear image references before clearing list
            for step_data in self.history:
                if 'before_screenshot' in step_data:
                    step_data['before_screenshot'] = None
                if 'after_screenshot' in step_data:
                    step_data['after_screenshot'] = None
                if 'before_raw_screenshot' in step_data:
                    step_data['before_raw_screenshot'] = None
                if 'after_raw_screenshot' in step_data:
                    step_data['after_raw_screenshot'] = None
            self.history.clear()

    def set_task_guidelines(self, task_guidelines: list[str]) -> None:
        self.additional_guidelines = task_guidelines

    def _log_model_output(self, source: str, prompt: str, response: str) -> None:
        if not self.raw_log_file:
            return
        entry = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "prompt": prompt,
            "response": response,
        }
        try:
            with open(self.raw_log_file, 'a', encoding='utf-8') as log_f:
                log_f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as exc:
            print(f"Failed to log model output: {exc}")
    
    def _save_screenshot(self, image, label: str):
        if image is None or not self.save_screenshots or self._screenshot_dir is None:
            try:
                if image:
                    image.close()
            except Exception:
                pass
            return None
        filename = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{self._screenshot_counter}_{label}.png"
        self._screenshot_counter += 1
        path = os.path.join(self._screenshot_dir, filename)
        try:
            image.save(path)
            return path
        except Exception as exc:
            print(f"Failed to save screenshot {label}: {exc}")
            return None
        finally:
            try:
                image.close()
            except Exception:
                pass

    def step(self) -> base_agent.AgentInteractionResult:
        conversation = []
        new_step_data = {
            'before_raw_screenshot': None,
            'after_raw_screenshot': None,
            'before_xml': None,
            'after_xml': None,
            'action_prompt': None,
            'action_output': None,
            'action_reason': None,
            'action_raw_response': None,
            'summary_prompt': None,
            'summary': None,
            'summary_raw_response': None,
        }
        if len(self.history) > 0 and self.summary_type in ("pre", "post", "pure_action"):
            last_step_data = self.history[-1]
            _, xml = self._get_screen()
            last_step_data['after_xml'] = xml
            # Do not save screenshots for xml_only summaries (text-only)
            last_step_data['after_screenshot'] = None
            last_step_data['after_raw_screenshot'] = None

            action_output = json.loads(last_step_data['action_output'])
            print("last_step_data['action_output']", action_output)

            if self.summary_type == "post" or self.summary_type == "pre":
                summary_prompt = self.prompts._summarize_prompt(
                    self.instruction,
                    last_step_data['action_output'],
                    last_step_data['action_reason'],
                    last_step_data['before_xml'],
                    last_step_data['after_xml'],
                    isxml=True,
                    summary_type=self.summary_type,
                    mm=False,
                )
                if(self.summary_type == "pre"):
                    if self.summary_model is not None:
                        summary, summary_generation = self.summary_model.query_mm(summary_prompt)
                        self._log_model_output("summary_model", summary_prompt, summary)
                    else:
                        summary = "Summary model not available"
                        summary_generation = None
                elif(self.summary_type == "post"):
                    if self.summary_model is not None:
                        summary, summary_generation = self.summary_model.query_mm(summary_prompt)
                        self._log_model_output("summary_model", summary_prompt, summary)
                    else:
                        summary = "Summary model not available"
                        summary_generation = None                       
                retry = 0
                max_retry = 3
                while (summary is None or summary == "") and retry < max_retry:
                    print('Summary prompt output is empty. Retrying...')
                    feedback = (
                        'Output for summary generation is empty. Try again.'
                        + "==== Original Summary Prompt ====\n"
                        + summary_prompt
                    )
                    time.sleep(1)
                    summary, summary_generation = self.model.query_mm(feedback, conversation)
                    self._log_model_output("summary_retry", feedback, summary)
                    conversation.append({"text": feedback})
                    conversation.append({"text": summary})
                    retry += 1

                last_step_data['summary_raw_response'] = summary
                last_step_data['summary_prompt'] = summary_prompt
                last_step_data['summary'] = (
                    f'Action selected: {last_step_data["action_output"]}. {summary}'
                )
                save_data = json.dumps({
                    "type": "summary",
                    "instruction": self.instruction,
                    "step": len(self.history) - 1,
                    "generation": summary_generation,
                })
            elif self.summary_type == "pure_action":
                last_step_data['summary'] = f'Action selected: {last_step_data["action_output"]}. '
                last_step_data['summary_raw_response'] = last_step_data['action_output']
                last_step_data['summary_prompt'] = None

                save_data = json.dumps({
                    "type": "summary",
                    "instruction": self.instruction,
                    "step": len(self.history) - 1,
                    "generation": None,
                })
            # Only write when summary payload exists
            if 'save_data' in locals() and save_data is not None:
                with open(os.path.join(self.env.results_path, "response.txt"), 'a') as f:
                    f.write(save_data + ',\n')
            
        self.history.append(new_step_data)
        step_data = self.history[-1]

        print('----------step ' + str(len(self.history)-1) + '----------')
        screenshot, xml = self._get_screen()
        step_data['before_xml'] = xml
        current_step_idx = len(self.history) - 1
        # Do not save screenshots for xml_only; keep only XML/text
        step_data['before_screenshot'] = None
        step_data['before_raw_screenshot'] = None

        # Build history lines safely even when summaries are missing (e.g., summary_type="none")
        history_lines = []
        for i, prev in enumerate(self.history[:-1]):
            summary_text = prev.get('summary')
            if not summary_text:
                ao = prev.get('action_output')
                summary_text = f"Action selected: {ao}" if ao else ""
            history_lines.append(f"Step {i + 1}: {summary_text}")

        action_prompt = self.prompts._action_selection_prompt(
            self.instruction,
            history_lines,
            xml,
            self.additional_guidelines,
            mm = False,
            isxml = True,
            prompt_type=self.prompt_type,

        )
        step_data['action_prompt'] = action_prompt
        raw_response, response_generation = self.model.query_mm(action_prompt)
        self._log_model_output("action", action_prompt, raw_response)
        conversation.append({"text": action_prompt})
        if (raw_response is None) or (raw_response == ""):
            max_retry = 3
            retry = 0
            while (raw_response is None or raw_response == "") and retry < max_retry:
                print('Action prompt output is empty. Retrying...')
                feedback = (
                    'Output for action selection is empty. Try again.'
                )
                time.sleep(1)
                raw_response, response_generation = self.model.query_mm(feedback, conversation)
                self._log_model_output("action_retry_empty", feedback, raw_response)
                print("#####################raw_response###############", raw_response)
                conversation.append({"text": feedback})
                conversation.append({"text": raw_response})
                retry += 1

        conversation.append({"text": raw_response})
        response = self._parse_response(raw_response, self.prompt_type)
        step_data['action_raw_response'] = raw_response

        # Check if the action prompt output is in the correct format.
        action = response['Action']
        reason = response['Reason']
        if (not action):
            max_retry = 3
            retry = 0
            while (not action) and retry < max_retry:
                print('Action prompt output is not in the correct format.')
                print("raw_response", raw_response)
                prompt_feedback = ""
                if self.prompt_type == "pure_action":
                    prompt_feedback = "Output should be in the format: {\"action_type\": \"<action_type>\", \"index\": <UI index>, \"params\": <params if you need>}\n"
                elif self.prompt_type == "react":
                    prompt_feedback = "Output should be in the format: {\"Reason\": \"<your reason>\", \"Action\": {\"action_type\": \"<action_type>\", \"index\": <UI index>, \"params\": <params if you need>}}\n"
                feedback = (
                    'Output for action selection is not in the correct format. Try again.'
                    + "==== Original Action Prompt ====\n"
                    + step_data['action_prompt']
                    + "follow the format strictly. Click/input actions must include the correct \"index\" referencing the UI element.\n"
                    + prompt_feedback
                )
                time.sleep(1)
                raw_response, response_generation = self.model.query_mm(feedback)
                self._log_model_output("action_retry_format", feedback, raw_response)
                conversation.append({"text": feedback})
                conversation.append({"text": raw_response})

                step_data['action_raw_response'] = raw_response
                response = self._parse_response(raw_response, self.prompt_type)
                action = response['Action']
                reason = response['Reason']
                retry += 1

        bbox = action.get("bounds", None)
        elem = self.env.parser.find_element_by_index(action['index']) if action['index'] is not None and type(action['index']) != dict else None
        if elem is not None:
            bbox = elem.get('bounds')

        action["bounds"] = str(bbox) if bbox is not None else None

        # -------------- reflection starts
        if(self.reflection_type == "pre" and self.reflection_agent is not None):
            self.reflection_agent.instruction = self.instruction
            self.reflection_agent.app_name = self.env.app_name
            correct = True
            correct, feedback, result = self.reflection_agent.pre_action_reflection(self.env.results_path,
                action, self.env.get_screenshot(), step_data['before_xml'], self.history
            )
            
            if not correct:
                print("Action is not correct. Retrying...")
                conversation.append({"text": feedback})
                time.sleep(1)
                raw_response, response_generation = self.reflection_model.query_mm(feedback, conversation = conversation)
                self._log_model_output("reflection", feedback, raw_response)
                conversation.append({"text": raw_response})
                response = self._parse_response(raw_response, self.prompt_type)
                action = response['Action']
                reason = response['Reason']
            # Log reflection verdicts similar to other agents
            ref_log_path = os.path.join(self.env.results_path, "reflection.txt")
            os.makedirs(self.env.results_path, exist_ok=True)
            with open(ref_log_path, 'a', encoding='utf-8') as rf:
                rf.write(json.dumps({
                    "step": len(self.history) - 1,
                    "instruction": self.instruction,
                    "verdict": correct,
                    "pre_action": action,
                    "post_action": action,
                    "pre_match": correct,
                    "post_match": correct,
                }, ensure_ascii=False) + ",\n")
        # -------------- reflection ends

        if action:
            bbox = action.get("bounds", None)
            elem = self.env.parser.find_element_by_index(action['index']) if action['index'] is not None and type(action['index']) != dict else None
            if elem is not None:
                bbox = elem.get('bounds')

            action["bounds"] = str(bbox)

        result: EnvInteractionResult = self.env.execute_action(action)

        if result.default_action:
            if 'params' in result.default_action:
                params = result.default_action.pop('params')
                result.default_action.update(params)
            summary_action = json.loads(json.dumps(result.default_action))
            summary_action['index'] = None
            step_data['action_output'] = json.dumps(summary_action)
            step_data['action_reason'] = ""
        else:
            summary_action = json.loads(json.dumps(response['Action']))
            summary_action['index'] = None
            step_data['action_output'] = json.dumps(summary_action)
            step_data['action_reason'] = response['Reason']
        

        save_data = json.dumps({
            "type": "step",
            "instruction": self.instruction,
            "step": len(self.history) - 1,
            "reason": reason,
            "action": action,
            "generation": response_generation,
        })
        with open(os.path.join(self.env.results_path, "response.txt"), 'a') as f:
            f.write(save_data + ',\n')

        return base_agent.AgentInteractionResult(
            done=result.done,
            success=result.success,
            data=AgentInteractionData(
                instruction=self.instruction,
                prompt=step_data['action_prompt'],
                screen=step_data['before_xml'],
                reason=reason,
                action=action,
            )
        )

    @classmethod
    def _parse_response(cls, raw_response: str, prompt_type: str) -> dict:

        default_return = {
            "Action": None,
            "Reason": "Not available"
        }
        
        if not raw_response:
            return default_return
        
        import re
        import json

        # Pattern to find a json object or a json array string.
        json_pattern = re.compile(r'(\[.*\]|\{.*\})', re.DOTALL)
        matches = json_pattern.findall(raw_response)
        print("matches", matches)

        if not matches:
            print("No JSON object or array found in the response.")
            return default_return

        match = matches[0]
        if match.startswith('{{') and match.endswith('}}'):
            match = match[1:-1]

        json_object = None
        try:
            loaded_json = json.loads(match)
            if isinstance(loaded_json, list):
                if loaded_json:
                    json_object = loaded_json[0]
                else:
                    print("Received an empty JSON list.")
                    return default_return
            else:
                json_object = loaded_json
        except json.JSONDecodeError as e:
            print(f"JSONDecodeError: Failed to parse the response: {e}")
            # Handle common error of extra data by truncating and retrying
            if "Extra data" in e.msg:
                try:
                    loaded_json = json.loads(match[:e.pos])
                    if isinstance(loaded_json, list):
                        if loaded_json:
                            json_object = loaded_json[0]
                        else:
                            return default_return
                    else:
                        json_object = loaded_json
                except json.JSONDecodeError as e2:
                    print(f"Failed to parse even after slicing: {e2}")
                    return default_return
            else:
                return default_return

        if not json_object:
            return default_return

        if prompt_type in ("pure_action", "few_shot", "scenario_shot"):
            action = {
                "action_type": json_object.get('action_type', None),
                "index": json_object.get('index', None),
                "params": json_object.get('params', "")
            }
            return {"Action": action, "Reason": "Not available"}
        
        elif prompt_type == "react":
            action_part = json_object.get('Action', {})
            reason = json_object.get('Reason', "Not available")
            
            action = {
                "action_type": action_part.get('action_type', None),
                "index": action_part.get('index', None),
                "params": action_part.get('params', "")
            }

            complete_action = {"Action": action, "Reason": reason}
            print("complete_action", complete_action)
            return complete_action
        
        return default_return
