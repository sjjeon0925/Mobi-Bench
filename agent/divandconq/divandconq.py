import json
import time
import os
from datetime import datetime
import re

from agent import base_agent
from agent.base_agent import Agent, AgentInteractionData

from environment.base_env import Env, EnvInteractionResult
from model.base_model import Model
from reflection_agent.pre_action_reflection import PreActionReflectionAgent
from prompts.agent_specific import seeact as seeact_prompts


class SeeActAgent(Agent):
    def __init__(
        self,
        model: Model,
        env: Env,
        prompt,
        summary_type: str = "post",
        reflection_type: str = "no_reflection",
        som_mode: str = "som",
        save_screenshots: bool = True,
        prompt_type: str = "react",
        summary_model: Model | None = None,
        reflection_model: Model | None = None,
    ):
        super().__init__(model, env, "seeact")
        self.name = "divandconq"
        self.history = []
        self.additional_guidelines: list[str] = []
        self.prompts = prompt
        self.summary_type = summary_type
        self.prompt_type = prompt_type
        self.reflection_type = reflection_type
        self.summary_model = summary_model
        self.reflection_model = reflection_model
        self.som_mode = som_mode  # "som" or "nosom"
        self.save_screenshots = save_screenshots
        os.makedirs(os.path.join("./results", self.name), exist_ok=True)
        # results_path will be provided per-task by benchmark; fallback if absent
        self.reflection_agent = None

    def set_task_guidelines(self, task_guidelines: list[str]) -> None:
        self.additional_guidelines = task_guidelines

    def reset(self, instruction: str):
        super().reset(instruction)
        for step_data in self.history:
            step_data["before_screenshot"] = None
            step_data["after_screenshot"] = None
            step_data["before_raw_screenshot"] = None
            step_data["after_raw_screenshot"] = None
        self.history.clear()

    def __del__(self):
        if hasattr(self, "history"):
            for step_data in self.history:
                step_data["before_screenshot"] = None
                step_data["after_screenshot"] = None
                step_data["before_raw_screenshot"] = None
                step_data["after_raw_screenshot"] = None
            self.history.clear()

    def _get_screen(self):
        if self.som_mode == "som":
            return self.env.get_screenshot_with_som()
        return self.env.get_screenshot_without_som()

    def step(self) -> base_agent.AgentInteractionResult:
        conversation = []
        new_step_data = {
            "before_screenshot": None,
            "before_raw_screenshot": None,
            "after_screenshot": None,
            "after_raw_screenshot": None,
            "before_structure": None,
            "after_structure": None,
            "plan_prompt": None,
            "plan_response": None,
            "action_prompt": None,
            "action_output": None,
            "action_reason": None,
            "action_raw_response": None,
            "summary_prompt": None,
            "summary": None,
            "summary_raw_response": None,
        }

        self.history.append(new_step_data)
        step_data = self.history[-1]

        screenshot, xml = self._get_screen()
        # Ensure results_path exists (benchmark sets per task; fallback here)
        if not self.env.results_path:
            self.env.results_path = os.path.join(
                "./results",
                self.name,
                f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{self.env.parser.name}_{self.som_mode}"
                f"_summary_{self.summary_type}_model_{self.model.name.replace('/', '-')}_prompt_{self.prompt_type}_reflect_{self.reflection_type}",
            )
        if self.save_screenshots:
            image_path = os.path.join(self.env.results_path, self.env.app_dir, self.env.task_name)
            os.makedirs(image_path, exist_ok=True)
            screenshot.save(os.path.join(image_path, f"step_{len(self.history) - 1}_before.png"))

        step_data["before_structure"] = xml
        step_data["before_screenshot"] = screenshot
        step_data["before_raw_screenshot"] = self.env.get_screenshot()

        history_lines = []
        for i, prev in enumerate(self.history[:-1]):
            summary_text = prev.get("summary")
            if not summary_text:
                ao = prev.get("action_output")
                summary_text = f"Action selected: {ao}" if ao else ""
            history_lines.append(f"Step {i + 1}: {summary_text}")

        plan_prompt = self._build_plan_prompt(history_lines, step_data["before_structure"])
        plan_response, plan_generation = self.model.query_mm(
            plan_prompt, [step_data["before_screenshot"]]
        )
        print("plan", plan_response)
        step_data["plan_prompt"] = plan_prompt
        step_data["plan_response"] = plan_response
        os.makedirs(self.env.results_path, exist_ok=True)
        # Log high-level reasoning separately
        with open(os.path.join(self.env.results_path, "response.txt"), "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "type": "reasoning",
                        "instruction": self.instruction,
                        "step": len(self.history) - 1,
                        "reason": plan_response,
                        "generation": plan_generation,
                    }
                )
                + ",\n"
            )
        conversation.append({"text": plan_prompt, "images": step_data["before_screenshot"]})
        conversation.append({"text": plan_response})

        extra_guidelines = list(self.additional_guidelines) if self.additional_guidelines else []
        if plan_response:
            extra_guidelines.append(f"See-Act plan: {plan_response}")

        action_prompt = self.prompts._action_selection_prompt(
            self.instruction,
            history_lines,
            step_data["before_structure"],
            extra_guidelines,
            mm=True,
            isxml=True,
            prompt_type=self.prompt_type,
        )
        step_data["action_prompt"] = action_prompt

        raw_response, response_generation = self.model.query_mm(
            action_prompt, [step_data["before_screenshot"]]
        )
        retry_count = 0
        print("action", raw_response)
        conversation.append({"text": action_prompt, "images": step_data["before_screenshot"]})
        conversation.append({"text": raw_response})

        if (raw_response is None) or (raw_response == ""):
            max_retry = 3
            retry = 0
            while (raw_response is None or raw_response == "") and retry < max_retry:
                print("Action prompt output is empty. Retrying...")
                feedback = "Output for action selection is empty. Try again."
                time.sleep(1)
                raw_response, response_generation = self.model.query_mm(feedback, conversation)
                print("action retry", raw_response)
                conversation.append({"text": feedback})
                conversation.append({"text": raw_response})
                retry += 1
                retry_count += 1

        conversation.append({"text": raw_response})
        # If model returns (text, meta), keep only the text part for parsing
        response_text = raw_response[0] if isinstance(raw_response, (list, tuple)) else raw_response
        response = self._parse_response(response_text, self.prompt_type)
        step_data["action_raw_response"] = raw_response

        action = response.get("Action", None)
        reason = response.get("Reason", None)
        if (not action) or (not reason):
            max_retry = 3
            retry = 0
            while (not action) or (not reason) and retry < max_retry:
                print("Action prompt output is not in the correct format.")
                feedback_header = (
                    'Output for action selection is not in the correct format. Try again.'
                    + '\nClick/input actions must include an "index" for the target UI element. Follow the format strictly.\n'
                )
                if self.prompt_type == "pure_action" or self.prompt_type == "few_shot":
                    prompt_feedback = 'Output should be in the format: {"action_type": "<action_type>", "index": <UI index>, "params": {<params if you need>}}\n'
                elif self.prompt_type in ("react", "f-react"):
                    prompt_feedback = 'Output should be in the format: {"Reason": "<your reason>", "Action": {"action_type": "<action_type>", "index": <UI index>, "params": {<params if you need>}}}\n'
                else:
                    prompt_feedback = ""
                feedback = (
                    feedback_header
                    + prompt_feedback
                    + "\n\n==== Original Action Prompt ====\n"
                    + step_data["action_prompt"]
                )
                time.sleep(1)
                raw_response, response_generation = self.model.query_mm(feedback, conversation)
                conversation.append({"text": feedback})
                conversation.append({"text": raw_response})
                step_data["action_raw_response"] = raw_response
                try:
                    response_text = raw_response[0] if isinstance(raw_response, (list, tuple)) else raw_response
                    response = self._parse_response(response_text, self.prompt_type)
                except json.JSONDecodeError:
                    print("Error: JSON parsing failed.")
                    response = {"Action": None, "Reason": None}
                action = response.get("Action", None)
                reason = response.get("Reason", None)
                retry += 1
                retry_count += 1

        bbox = action.get("bounds", None) if action else None
        if bbox is None and action is not None:
            bbox = action.get("bbox", None)
        if bbox is None and action is not None:
            elem = (
                self.env.parser.find_element_by_index(action["index"])
                if action["index"] is not None and not isinstance(action["index"], dict)
                else None
            )
            if elem is not None:
                bbox = elem.get("bounds")
        if action is not None:
            action["bounds"] = str(bbox)

        if self.reflection_type == "pre" and self.reflection_agent is not None and action is not None:
            pre_action_copy = json.loads(json.dumps(action))
            self.reflection_agent.instruction = self.instruction
            self.reflection_agent.app_name = self.env.app_name
            correct, feedback, result = self.reflection_agent.pre_action_reflection(
                self.env.results_path,
                action,
                step_data["before_screenshot"],
                step_data["before_structure"],
                self.history,
            )
            if not correct:
                print("Action is not correct. Retrying...")
                conversation.append({"text": feedback})
                time.sleep(1)
                raw_response, response_generation = self.reflection_model.query_mm(
                    feedback, conversation=conversation
                )
                conversation.append({"text": raw_response})
                response = self._parse_response(raw_response, self.prompt_type)
                action = response.get("Action", None)
                reason = response.get("Reason", None)
            # reflection log (similar format to other agents)
            ref_log_path = os.path.join(self.env.results_path, "reflection.txt")
            os.makedirs(self.env.results_path, exist_ok=True)
            with open(ref_log_path, "a", encoding="utf-8") as rf:
                rf.write(
                    json.dumps(
                        {
                            "step": len(self.history) - 1,
                            "instruction": self.instruction,
                            "verdict": correct,
                            "pre_action": pre_action_copy,
                            "post_action": action,
                            "pre_match": correct,
                            "post_match": correct,
                        },
                        ensure_ascii=False,
                    )
                    + ",\n"
                )

        result: EnvInteractionResult = self.env.execute_action(action)

        # Use gold/default action for summary/logging when available.
        # For summary, drop index to avoid mismatches; keep bounds/params.
        summary_action = None
        summary_reason = "" if result.default_action else response.get("Reason")
        if result.default_action:
            summary_action = json.loads(json.dumps(result.default_action))
            summary_action["index"] = None
        else:
            summary_action = json.loads(json.dumps(response.get("Action"))) if response.get("Action") else None
            if summary_action is not None:
                summary_action["index"] = None

        if result.default_action:
            if "params" in result.default_action:
                params = result.default_action.pop("params")
                result.default_action.update(params)
            step_data["action_output"] = json.dumps(result.default_action)
            step_data["action_reason"] = ""
        else:
            step_data["action_output"] = json.dumps(response["Action"])
            step_data["action_reason"] = response["Reason"]

        step_data["summary_action"] = summary_action
        step_data["summary_reason"] = summary_reason

        # Grounding log (action-level)
        save_data = json.dumps(
            {
                "type": "grounding",
                "instruction": self.instruction,
                "step": len(self.history) - 1,
                "reason": raw_response if isinstance(raw_response, str) else raw_response[0] if isinstance(raw_response, (list, tuple)) else raw_response,
                "action": action,
                "generation": response_generation,
                "plan_generation": plan_generation,
                "retry_count": retry_count,
            }
        )

        os.makedirs(self.env.results_path, exist_ok=True)
        with open(os.path.join(self.env.results_path, "response.txt"), "a", encoding="utf-8") as f:
            f.write(save_data + ",\n")

        result_screenshot = step_data["before_screenshot"]
        self._finalize_step(len(self.history) - 1)

        return base_agent.AgentInteractionResult(
            done=result.done,
            success=result.success,
            data=AgentInteractionData(
                instruction=self.instruction,
                prompt=step_data["action_prompt"],
                screen=step_data["before_structure"],
                reason=reason,
                action=action,
                screenshot=result_screenshot,
                retry_count=retry_count,
            ),
        )

    def _build_plan_prompt(self, history_lines: list[str], ui_elements: str | None) -> str:
        base_prompt = seeact_prompts.generate_action_generation_prompt(
            self.instruction,
            seeact_prompts.SEEACT_PROMPT_GUIDELINE,
            previous_actions=history_lines if history_lines else None,
        )
        ui_text = ui_elements if ui_elements else "Not available"
        return (
            seeact_prompts.SEEACT_PROMPT_PREFIX
            + "\n"
            + base_prompt
            + "\n\nHere is a representation of UI elements on the current screen:\n"
            + ui_text
        )

    def _finalize_step(self, step_index: int) -> None:
        if step_index < 0 or step_index >= len(self.history):
            return
        step_data = self.history[step_index]
        if step_data.get("_finalized"):
            return

        summary_payload = None
        summary_generation = None
        if self.summary_type in ("pre", "post"):
            capture_after = True
            env_has_sequence = hasattr(self.env, "screenshots") and isinstance(
                getattr(self.env, "screenshots", None), list
            )
            if env_has_sequence:
                total_screens = len(getattr(self.env, "screenshots"))
                current_step = getattr(self.env, "current_step", 0)
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
                step_data["after_structure"] = xml
                step_data["after_screenshot"] = screenshot
                try:
                    step_data["after_raw_screenshot"] = self.env.get_screenshot()
                except (IndexError, FileNotFoundError):
                    step_data["after_raw_screenshot"] = None
                    capture_after = False
            else:
                step_data["after_structure"] = step_data.get("after_structure")
                step_data["after_screenshot"] = None
                step_data["after_raw_screenshot"] = None

            if self.summary_model is not None:
                summary_prompt = self.prompts._summarize_prompt(
                    self.instruction,
                    json.dumps(step_data.get("summary_action")) if step_data.get("summary_action") is not None else step_data["action_output"],
                    step_data.get("summary_reason"),
                    step_data["before_structure"],
                    step_data["after_structure"]
                    if step_data["after_structure"] is not None
                    else step_data["before_structure"],
                    isxml=True,
                    mm=True,
                    summary_type=self.summary_type,
                )
                if self.summary_type == "pre":
                    summary, summary_generation = self.summary_model.query_mm(
                        summary_prompt, step_data["before_screenshot"]
                    )
                elif self.summary_type == "post" and step_data["after_screenshot"] is not None:
                    summary, summary_generation = self.summary_model.query_mm(
                        summary_prompt,
                        [step_data["before_screenshot"], step_data["after_screenshot"]],
                    )
                else:
                    summary = "Summary skipped (after screenshot unavailable)."
                step_data["summary_prompt"] = summary_prompt
                step_data["summary_raw_response"] = summary
                step_data["summary"] = f"{summary}"
                summary_payload = json.dumps(
                    {
                        "type": "summary",
                        "instruction": self.instruction,
                        "step": step_index,
                        "generation": summary_generation
                        if self.summary_model is not None
                        else None,
                    }
                )
            else:
                step_data["summary"] = f'Action selected: {step_data["action_output"]}. '
                step_data["summary_raw_response"] = step_data["action_output"]
                step_data["summary_prompt"] = None
                summary_payload = json.dumps(
                    {
                        "type": "summary",
                        "instruction": self.instruction,
                        "step": step_index,
                        "generation": None,
                    }
                )
        elif self.summary_type == "pure_action":
            step_data["summary"] = f'Action selected: {step_data["action_output"]}. '
            step_data["summary_raw_response"] = step_data["action_output"]
            step_data["summary_prompt"] = None
            summary_payload = json.dumps(
                {
                    "type": "summary",
                    "instruction": self.instruction,
                    "step": step_index,
                    "generation": None,
                }
            )

        if summary_payload is not None:
            with open(os.path.join(self.env.results_path, "response.txt"), "a") as f:
                f.write(summary_payload + ",\n")

        step_data["before_screenshot"] = None
        step_data["before_raw_screenshot"] = None
        step_data["after_screenshot"] = None
        step_data["after_raw_screenshot"] = None
        step_data["_finalized"] = True

    @classmethod
    def _parse_response(cls, raw_response: str, prompt_type: str) -> dict:
        """
        Parses raw model output into {"Action": {...}, "Reason": "..."}.
        - Supports plain JSON (pure_action) or React-style {"Reason":..., "Action":{...}}.
        - If index is a dict, merges it into params and clears index.
        """
        default_return = {"Action": None, "Reason": "Not available"}
        if raw_response is None:
            return default_return

        # First try direct JSON load of the full response
        try:
            obj = json.loads(raw_response)
            if isinstance(obj, dict):
                action = None
                reason = obj.get("Reason", "Not available")
                if "Action" in obj and isinstance(obj["Action"], dict):
                    action = obj["Action"]
                elif "action_type" in obj:
                    action = obj
                if action is not None:
                    idx = action.get("index")
                    params = action.get("params", {}) or {}
                    if isinstance(idx, dict):
                        params.update(idx)
                        idx = None
                    return {"Action": {"action_type": action.get("action_type"), "index": idx, "params": params}, "Reason": reason}
        except Exception:
            pass

        # Extract JSON blocks
        matches = re.findall(r"\{.*?\}", raw_response, re.DOTALL)
        if not matches:
            print("No JSON found in response.")
            return default_return

        for m in matches:
            try:
                obj = json.loads(m)
            except json.JSONDecodeError:
                continue

            # React/f-react shape
            if "Action" in obj:
                action = obj.get("Action", {}) or {}
                reason = obj.get("Reason", "Not available")
            else:
                action = obj
                reason = "Not available"

            if not isinstance(action, dict):
                continue

            # Move dict index into params
            idx = action.get("index")
            params = action.get("params", {}) or {}
            if isinstance(idx, dict):
                params.update(idx)
                idx = None

            parsed_action = {
                "action_type": action.get("action_type"),
                "index": idx,
                "params": params,
            }
            return {"Action": parsed_action, "Reason": reason}

        return default_return
