import json
import os
from PIL import Image

from agent import base_agent
from agent.base_agent import Agent, AgentInteractionData
from environment.base_env import Env, EnvInteractionResult
from model.base_model import Model
from utils import parse_json

class ImageOnlyAgent(Agent):
    def __init__(self, model: Model, env: Env, prompt, prompt_type: str = "react"):
        super().__init__(model, env, 'image-only')
        self.history = []
        self.additional_guidelines = None
        self.prompts = prompt
        self.prompt_type = prompt_type

    def reset(self, instruction: str):
        super().reset(instruction)
        self.history = []

    def set_task_guidelines(self, task_guidelines: list[str]) -> None:
        self.additional_guidelines = task_guidelines

    def step(self) -> base_agent.AgentInteractionResult:
        conversation = []
        step_data = {}
        self.history.append(step_data)

        print('----------step ' + str(len(self.history)-1) + '----------')
        screenshot = self.env.get_screenshot()
        step_data['before_screenshot'] = screenshot

        history_summaries = []
        if len(self.history) > 1:
            for h in self.history[:-1]:
                # Simplified text-based summary for history
                summary = h.get('summary', f"Action: {h.get('action_output', 'N/A')}")
                history_summaries.append(summary)

        action_prompt = self.prompts._action_selection_prompt(
            self.instruction,
            history_summaries,
            ui_elements_description="",  # No XML/text descriptions
            additional_guidelines=self.additional_guidelines,
            mm=True,
            prompt_type=self.prompt_type,
            image_only=True,  # Use the image-only prompt variations
        )
        step_data['action_prompt'] = action_prompt
        
        raw_response, response_generation = self.model.query_mm(action_prompt, [screenshot])
        conversation.append({"text": action_prompt, "images": [screenshot]})
        conversation.append({"text": raw_response})
        
        step_data['action_raw_response'] = raw_response

        # Basic retry for empty response
        retry = 0
        while not raw_response and retry < 3:
            print('Action prompt output is empty. Retrying...')
            raw_response, response_generation = self.model.query_mm("Output is empty. Please try again.", conversation)
            conversation.append({"text": raw_response})
            step_data['action_raw_response'] = raw_response
            retry += 1
            
        response = self._parse_response(raw_response, screenshot, self.prompt_type)
        print("raw_response:", raw_response)
        action = response.get('Action')
        reason = response.get('Reason', "")
    
        # Basic retry for malformed action
        retry = 0
        while not action and retry < 3:
            print('Action prompt output is not in the correct format. Retrying...')
            feedback = 'Output for action selection is not in the correct format. You must follow the JSON format. Try again.'
            raw_response, response_generation = self.model.query_mm(feedback, conversation)
            conversation.append({"text": feedback})
            conversation.append({"text": raw_response})
            step_data['action_raw_response'] = raw_response
            response = self._parse_response(raw_response, screenshot, self.prompt_type)
            print("raw_response:", raw_response)
            action = response.get('Action')
            reason = response.get('Reason', "")
            retry += 1
        
        if not action:
            # Default to finish if action cannot be parsed
            action = {"action_type": "finish", "status": "error"}

        step_data['action_output'] = json.dumps(action)
        step_data['action_reason'] = reason
        summary_text = f"Action: {action}"
        reason_text = (reason or '').strip()
        if reason_text:
            summary_text += f" | {reason_text}"
        step_data['summary'] = summary_text

        result: EnvInteractionResult = self.env.execute_action(action)

        # Logging to response.txt
        try:
            os.makedirs(self.env.results_path, exist_ok=True)
            save_data = json.dumps({
                "type": "step",
                "instruction": self.instruction,
                "step": len(self.history) - 1,
                "reason": reason,
                "action": action,
                "generation": response_generation,
            })
            with open(os.path.join(self.env.results_path, "response.txt"), 'a', encoding='utf-8') as f:
                f.write(save_data + ',\n')
        except Exception as e:
            print(f"Error saving step data: {e}")

        return base_agent.AgentInteractionResult(
            done=result.done, 
            success=result.success, 
            data = AgentInteractionData(
                instruction=self.instruction,
                screen="image_only",
                prompt=step_data['action_prompt'],
                reason=reason,
                action=action,
                screenshot=step_data['before_screenshot']
            )
        )

    def _parse_response(self, raw_response: str, screenshot: Image.Image, prompt_type: str) -> dict:
        if isinstance(raw_response, (list, tuple)) and raw_response:
            raw_response = raw_response[0]

        def _extract_first_json(payload: str):
            if not isinstance(payload, str):
                return None
            decoder = json.JSONDecoder()
            idx = 0
            length = len(payload)
            while idx < length:
                ch = payload[idx]
                if ch not in '{[':
                    idx += 1
                    continue
                try:
                    obj, offset = decoder.raw_decode(payload[idx:])
                    return obj
                except json.JSONDecodeError:
                    idx += 1
            return None

        try:
            json_formatted_response = parse_json(raw_response) or {}
        except json.JSONDecodeError:
            json_formatted_response = {}

        if isinstance(json_formatted_response, list) and json_formatted_response:
            json_formatted_response = json_formatted_response[0]

        action_data = json_formatted_response.get('Action') if isinstance(json_formatted_response, dict) else {}
        reason = json_formatted_response.get('Reason', "") if isinstance(json_formatted_response, dict) else ""

        # Pure-action prompts return a single JSON object; fall back to direct parsing
        if not action_data and prompt_type in ("pure_action", "few_shot", "scenario_shot"):
            fallback_obj = None
            try:
                fallback_obj = json.loads(raw_response)
            except (json.JSONDecodeError, TypeError):
                fallback_obj = _extract_first_json(raw_response)

            if isinstance(fallback_obj, list) and fallback_obj:
                fallback_obj = fallback_obj[0]

            if isinstance(fallback_obj, dict):
                if 'Action' in fallback_obj and isinstance(fallback_obj['Action'], dict):
                    action_data = fallback_obj['Action']
                    reason = fallback_obj.get('Reason', reason)
                elif 'action_type' in fallback_obj:
                    action_data = fallback_obj
                    reason = fallback_obj.get('Reason', reason)

        if not isinstance(action_data, dict):
            action_data = {}

        final_action = {}
        action_type = action_data.get('action_type')
        if action_type is None:
            return {"Action": None, "Reason": reason or ""}

        final_action['action_type'] = action_type

        if action_type == 'click':
            normalized_coords = action_data.get('coordinates')
            # Always set index to -1 for image-only click actions
            final_action['index'] = -1

            if isinstance(normalized_coords, list) and len(normalized_coords) == 2:
                # Rescale normalized coordinates to absolute pixel coordinates
                try:
                    width, height = screenshot.size
                    y_norm, x_norm = normalized_coords
                    # Clamp values to be safe
                    y_norm = max(0.0, min(1.0, y_norm))
                    x_norm = max(0.0, min(1.0, x_norm))
                    abs_x = int(x_norm * width)
                    abs_y = int(y_norm * height)
                    # Create a point-bounds string instead of coordinates
                    final_action['bounds'] = f"[{abs_x},{abs_y}][{abs_x},{abs_y}]"
                except (ValueError, TypeError):
                    # If coordinates are invalid, do not add bounds
                    pass
            # No 'coordinates' key should be in the final action

        elif action_type == 'input':
            # Input action does not have an index in image-only mode
            final_action['params'] = action_data.get('params', {})
            final_action['index'] = -1

            normalized_coords = action_data.get('coordinates')
            if isinstance(normalized_coords, list) and len(normalized_coords) == 2:
                # Rescale normalized coordinates to absolute pixel coordinates
                try:
                    width, height = screenshot.size
                    y_norm, x_norm = normalized_coords
                    # Clamp values to be safe
                    y_norm = max(0.0, min(1.0, y_norm))
                    x_norm = max(0.0, min(1.0, x_norm))
                    abs_x = int(x_norm * width)
                    abs_y = int(y_norm * height)
                    # Create a point-bounds string instead of coordinates
                    final_action['bounds'] = f"[{abs_x},{abs_y}][{abs_x},{abs_y}]"
                except (ValueError, TypeError):
                    # If coordinates are invalid, do not add bounds
                    pass
            # No 'coordinates' key should be in the final action
        else:
            # For other actions like scroll, navigate_back, finish, copy structure
            final_action.update(action_data)
            # Ensure index is not carried over unless explicitly handled
            if 'index' not in final_action:
                final_action['index'] = -1

        # Remove intermediate fields that the environment does not expect
        final_action.pop('coordinates', None)

        if isinstance(reason, str) and reason.strip() == (raw_response or '').strip():
            reason = ''

        return {"Action": final_action, "Reason": reason}
