import json
import ast
import time
from agent import base_agent
from agent.base_agent import Agent, AgentInteractionData

from environment.base_env import Env, EnvInteractionResult
from model.base_model import Model
from utils import parse_json
import os

from datetime import datetime
from reflection_agent.pre_action_reflection import PreActionReflectionAgent

class ImageWithExplanationAgent(Agent):
    def __init__(self, model: Model, reflection_model: Model, summary_model: Model, env: Env, prompt, summary_type: str = "post", prompt_type: str = "react", reflection_type: str = "no_reflection", som_mode: str = "som", save_screenshots: bool = True):
        super().__init__(model, env, "image_with_explanation")
        self.name = "iwe"
        self.history = []
        self.additional_guidelines = []
        self.prompts = prompt
        self.summary = None
        self.reflection_type = reflection_type
        self.summary_type = summary_type
        self.prompt_type = prompt_type
        self.summary_model = summary_model
        self.reflection_model = reflection_model
        self.env = env
        print("prompt_type", self.prompt_type)
        self.som_mode = som_mode  # "som" or "nosom"
        self.save_screenshots = save_screenshots
        self.results_path = None
        os.makedirs(os.path.join("./results", self.name), exist_ok=True)
        self.env.results_path = os.path.join("./results", self.name, f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{self.env.parser.name}_{self.som_mode}_summary_{self.summary_type}_model_{self.model.name.replace('/', '-')}_prompt_{self.prompt_type}_reflect_{self.reflection_type}")
        os.makedirs(self.env.results_path, exist_ok=True)

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
            step_data['before_screenshot'] = None
            step_data['after_screenshot'] = None
            step_data['before_raw_screenshot'] = None
            step_data['after_raw_screenshot'] = None
        # Then clear the list for new task
        self.history.clear()
        
    def __del__(self):
        """Cleanup method to free memory when agent is destroyed."""
        if hasattr(self, 'history'):
            # Clear image references before clearing list
            for step_data in self.history:
                step_data['before_screenshot'] = None
                step_data['after_screenshot'] = None
                step_data['before_raw_screenshot'] = None
                step_data['after_raw_screenshot'] = None
            self.history.clear()

    def set_task_guidelines(self, task_guidelines: list[str]) -> None:
        self.additional_guidelines = task_guidelines

    def step(self) -> base_agent.AgentInteractionResult:
        conversation = []
        new_step_data = {
            'before_screenshot': None,
            'before_raw_screenshot': None,
            'after_screenshot': None,
            'after_raw_screenshot': None,
            'before_structure': None,
            'after_structure': None,
            'action_prompt': None,
            'action_output': None,
            'action_reason': None,
            'action_raw_response': None,
            'summary_prompt': None,
            'summary': None,
            'summary_raw_response': None,
            'retry_count': 0,
        }

        # Start a new step
        self.history.append(new_step_data)
        step_data = self.history[-1]

        # Get screenshot + SoM + parser XML
        screenshot, xml = self._get_screen()

        if self.save_screenshots:
            image_path = os.path.join(self.env.results_path, self.env.app_dir, self.env.task_name)
            os.makedirs(image_path, exist_ok=True)
            screenshot.save(os.path.join(image_path, f"step_{len(self.history)-1}_before.png"))

        step_data['before_structure'] = xml
        step_data['before_screenshot'] = screenshot
        step_data['before_raw_screenshot'] = self.env.get_screenshot()
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
            step_data['before_structure'],
            self.additional_guidelines,
            mm=True,
            isxml=True,
            prompt_type=self.prompt_type,
        )
        step_data['action_prompt'] = action_prompt

        # Model action selection
        retry_count = 0
        raw_response, response_generation = self.model.query_mm(action_prompt, [step_data['before_screenshot']])

        # Conversation context
        conversation.append({"text": action_prompt, "images": step_data['before_screenshot']})

        # Retry if empty response
        if (raw_response is None) or (raw_response == ""):
            max_retry = 3
            retry = 0
            while (raw_response is None or raw_response == "") and retry < max_retry:
                print('Action prompt output is empty. Retrying...')
                feedback = 'Output for action selection is empty. Try again.'
                time.sleep(1)
                raw_response, response_generation = self.model.query_mm(feedback, conversation)
                conversation.append({"text": feedback})
                conversation.append({"text": raw_response})
                retry += 1
                retry_count += 1

        conversation.append({"text": raw_response})
        response = self._parse_response(raw_response, self.prompt_type)
        step_data['action_raw_response'] = raw_response

        # Validate format
        action = response.get('Action', None)
        reason = response.get('Reason', None)
        if (not action) or (not reason):
            max_retry = 3
            retry = 0
            while (not action) or (not reason) and retry < max_retry:
                print('Action prompt output is not in the correct format.')
                if self.prompt_type == "pure_action":
                    prompt_feedback = "Output should be in the format: {\"action_type\": \"<action_type>\", \"index\": <UI index>, \"params\": {<params if you need>}}\n"
                elif self.prompt_type == "react":
                    prompt_feedback = "Output should be in the format: {\"Reason\": \"<your reason>\", \"Action\": {\"action_type\": \"<action_type>\", \"index\": <UI index>, \"params\": {<params if you need>}}}\n"
                else:
                    prompt_feedback = ""
                feedback = (
                    'Output for action selection is not in the correct format. Try again.'
                    + "\nClick/input actions must include an \"index\" for the target UI element. Follow the format strictly.\n"
                    + prompt_feedback
                    + "\n\n==== Original Action Prompt ====\n"
                    + step_data['action_prompt']
                )
                time.sleep(1)
                raw_response, response_generation = self.model.query_mm(feedback, conversation)
                conversation.append({"text": feedback})
                conversation.append({"text": raw_response})

                step_data['action_raw_response'] = raw_response
                try:
                    response = self._parse_response(raw_response, self.prompt_type)
                except json.JSONDecodeError:
                    print("Error: JSON parsing failed.")
                    response = {"Action": None, "Reason": None}
                action = response.get('Action', None)
                reason = response.get('Reason', None)
                retry += 1
                retry_count += 1

        # Fill bounds if missing
        bbox = action.get("bounds", None) if action else None
        if bbox is None:
            bbox = action.get('bbox', None) if action else None
        if bbox is None and action is not None:
            elem = self.env.parser.find_element_by_index(action['index']) if action['index'] is not None and type(action['index']) != dict else None
            if elem is not None:
                bbox = elem.get('bounds')
        if action is not None:
            action["bounds"] = str(bbox)

        # Optional reflection before executing
        if self.reflection_type == "pre" and self.reflection_agent is not None and action is not None:
            self.reflection_agent.instruction = self.instruction
            self.reflection_agent.app_name = self.env.app_name
            correct = True
            pre_reflection_action = json.loads(json.dumps(action))
            correct, feedback, result = self.reflection_agent.pre_action_reflection(
                self.env.results_path,
                action,
                step_data['before_screenshot'],
                step_data['before_structure'],
                self.history
            )
            if not correct:
                print("Action is not correct. Retrying...")
                conversation.append({"text": feedback})
                time.sleep(1)
                raw_response, response_generation = self.reflection_model.query_mm(feedback, conversation=conversation)
                conversation.append({"text": raw_response})
                response = self._parse_response(raw_response, self.prompt_type)
                action = response.get('Action', None)
                reason = response.get('Reason', None)
            if action is not None:
                action["reflection_info"] = {
                    "pre_action": pre_reflection_action,
                    "post_action": json.loads(json.dumps(action)),
                    "verdict": correct,
                }

        # Execute action
        result: EnvInteractionResult = self.env.execute_action(action)
        # if result.feedback:
        #     max_retry = 3
        #     retry = 0
        #     while result.feedback and retry < max_retry:
        #         # Success can be true if the action is "request_approval".
        #         if not result.success:
        #             retry += 1
        #         conversation.append({"text": result.feedback})

        #         step_data['action_raw_response'] = raw_response
        #         response = self._parse_response(raw_response)
        #         action = response['Action']
        #         reason = response['Reason']
        #         result: EnvInteractionResult = self.env.execute_action(action['action_type'], index=action['index'], params=action['params'])

        if result.default_action:
            # Decouple params dictionary into default_action
            if 'params' in result.default_action:
                params = result.default_action.pop('params')
                result.default_action.update(params)
            # For summary/logging, drop index to avoid parser mismatch; keep bounds/params.
            summary_action = json.loads(json.dumps(result.default_action)) if result.default_action else {}
            if isinstance(summary_action, dict):
                summary_action['index'] = None
            step_data['action_output'] = json.dumps(summary_action)
            step_data['action_reason'] = ""
        else:
            # Model action case: also drop index in summary/logging.
            model_action = response.get('Action') if isinstance(response, dict) else None
            summary_action = json.loads(json.dumps(model_action)) if model_action else {}
            if isinstance(summary_action, dict):
                summary_action['index'] = None
            step_data['action_output'] = json.dumps(summary_action)
            step_data['action_reason'] = response.get('Reason') if isinstance(response, dict) else ""
        print("step data\n", step_data['action_output'], step_data['action_reason'])

        print("response_generation", response_generation)

        def _json_safe(val):
            """Best-effort conversion to JSON-serializable form for logging."""
            if isinstance(val, dict):
                return {k: _json_safe(v) for k, v in val.items()}
            if isinstance(val, list):
                return [_json_safe(v) for v in val]
            try:
                json.dumps(val)
                return val
            except Exception:
                return str(val)

        generation_log = _json_safe(response_generation)

        step_data['retry_count'] = retry_count

        save_data = json.dumps({
            "type": "step",
            "instruction": self.instruction,
            "step": len(self.history) - 1,
            "reason": reason,
            "action": action,
            "generation": generation_log,
            "retry_count": retry_count
        })
        
        with open(os.path.join(self.env.results_path, "response.txt"), 'a') as f:
            f.write(save_data + ',\n')

        result_screenshot = step_data['before_screenshot']
        self._finalize_step(len(self.history) - 1)

        return base_agent.AgentInteractionResult(
            done=result.done, 
            success=result.success, 
            data = AgentInteractionData(
                instruction=self.instruction,
                prompt=step_data['action_prompt'],
                screen=step_data['before_structure'],
                reason=reason,
                action=action,
                screenshot=result_screenshot,
                retry_count=retry_count
            ))    
    
    def _finalize_step(self, step_index: int) -> None:
        if step_index < 0 or step_index >= len(self.history):
            return

        step_data = self.history[step_index]
        if step_data.get('_finalized'):
            return

        summary_payload = None
        summary_generation = None

        if self.summary_type in ("pre", "post"):
            capture_after = True
            env_has_sequence = hasattr(self.env, 'screenshots') and isinstance(getattr(self.env, 'screenshots', None), list)
            if env_has_sequence:
                total_screens = len(getattr(self.env, 'screenshots'))
                current_step = getattr(self.env, 'current_step', 0)
                if total_screens == 0 or current_step >= total_screens:
                    capture_after = False

            if capture_after:
                try:
                    screenshot, xml = self._get_screen()
                except (IndexError, FileNotFoundError):
                    capture_after = False
                    screenshot = None
                    xml = None
            else:
                screenshot = None
                xml = None

            if capture_after:
                step_data['after_structure'] = xml
                step_data['after_screenshot'] = screenshot
                try:
                    step_data['after_raw_screenshot'] = self.env.get_screenshot()
                except (IndexError, FileNotFoundError):
                    step_data['after_raw_screenshot'] = None
                    capture_after = False
            else:
                step_data['after_structure'] = step_data.get('after_structure')
                step_data['after_screenshot'] = None
                step_data['after_raw_screenshot'] = None

            summary_prompt = self.prompts._summarize_prompt(
                self.instruction,
                step_data['action_output'],
                step_data['action_reason'],
                step_data['before_structure'],
                step_data['after_structure'] if step_data['after_structure'] is not None else step_data['before_structure'],
                isxml=True,
                mm=True,
                summary_type=self.summary_type,
            )

            if self.summary_model is not None:
                if self.summary_type == "pre":
                    summary, summary_generation = self.summary_model.query_mm(summary_prompt, step_data['before_screenshot'])
                elif self.summary_type == "post" and step_data['after_screenshot'] is not None:
                    summary, summary_generation = self.summary_model.query_mm(summary_prompt, [step_data['before_screenshot'], step_data['after_screenshot']])
                else:
                    summary = "Summary skipped (after screenshot unavailable)."
                    summary_generation = None
            else:
                summary = "Summary model not available"

            step_data['summary_prompt'] = summary_prompt
            step_data['summary_raw_response'] = summary
            step_data['summary'] = f'{summary}'
            def _json_safe(val):
                if isinstance(val, dict):
                    return {k: _json_safe(v) for k, v in val.items()}
                if isinstance(val, list):
                    return [_json_safe(v) for v in val]
                try:
                    json.dumps(val)
                    return val
                except Exception:
                    return str(val)

            summary_generation_log = _json_safe(summary_generation) if self.summary_model is not None else None

            summary_payload = json.dumps({
                "type": "summary",
                "instruction": self.instruction,
                "step": step_index,
                "generation": summary_generation_log,
            })
        elif self.summary_type == "pure_action":
            step_data['summary'] = f'Action selected: {step_data["action_output"]}. '
            step_data['summary_raw_response'] = step_data['action_output']
            step_data['summary_prompt'] = None
            summary_payload = json.dumps({
                "type": "summary",
                "instruction": self.instruction,
                "step": step_index,
                "generation": None,
            })

        if summary_payload is not None:
            with open(os.path.join(self.env.results_path, "response.txt"), 'a') as f:
                f.write(summary_payload + ',\n')

        # Clear heavy image references once they are no longer needed
        step_data['before_screenshot'] = None
        step_data['before_raw_screenshot'] = None
        step_data['after_screenshot'] = None
        step_data['after_raw_screenshot'] = None
        step_data['_finalized'] = True

    @classmethod
    def _parse_response(cls, raw_response: str, prompt_type: str) -> dict:

        default_return = {
            "Action": None,
            "Reason": "Not available"
        }
        
        if(raw_response == None):
            return default_return
        
        # Collect candidate JSON snippets (handles multiple JSON objects separated by newlines)
        candidates = []
        # full string first
        candidates.append(raw_response)
        # split by lines
        candidates.extend([line for line in raw_response.splitlines() if line.strip()])
        # regex non-greedy matches
        import re
        pattern = re.compile(r'\{.*?\}', re.DOTALL)
        candidates.extend([m.group(0) for m in pattern.finditer(raw_response)])

        def try_parse(obj_str: str):
            for loader in (json.loads, ast.literal_eval):
                try:
                    obj = loader(obj_str)
                    return obj
                except Exception:
                    continue
            return None

        def normalize_obj(obj):
            # unwrap list/tuple if single element
            if isinstance(obj, (list, tuple)) and obj:
                return obj[0]
            return obj

        if prompt_type in ("pure_action", "few_shot", "scenario_shot"):
            for cand in candidates:
                obj = normalize_obj(try_parse(cand))
                if not isinstance(obj, dict):
                    continue
                extracted_action = {
                    "action_type": obj.get('action_type'),
                    "index": obj.get('index'),
                    "params": obj.get('params', "")}
                atype = extracted_action.get('action_type')
                if atype in ['click', 'long_click', 'input'] and extracted_action.get("index") is None:
                    continue
                return {"Action": extracted_action, "Reason": "Not available"}
            print("No valid pure_action JSON found; falling back to default.")
            return default_return

        elif prompt_type in ("react", "f-react"):
            for cand in candidates:
                obj = normalize_obj(try_parse(cand))
                if not isinstance(obj, dict):
                    continue
                extracted_action = obj.get('Action', {})
                extracted_reason = obj.get('Reason', "Not available")
                if not isinstance(extracted_action, dict):
                    continue
                atype = extracted_action.get('action_type')
                if atype in ['click', 'long_click', 'input'] and extracted_action.get("index") is None:
                    continue
                complete_action = {
                    "Action": {
                        "action_type": extracted_action.get('action_type'),
                        "index": extracted_action.get('index'),
                        "params": extracted_action.get('params', "")
                    },
                    "Reason": extracted_reason
                }
                print("complete_action", complete_action)
                return complete_action
            print("No valid react JSON found; falling back to default.")
            return default_return

        return default_return
