# Base benchmark utilities.

import abc
import json
import os
import textwrap
from agent.base_agent import Agent, AgentInteractionResult
from environment.base_env import Env
from PIL import ImageDraw, ImageFont

class Benchmark:
    def __init__(self, name: str, env: Env, agent: Agent):
        self.name = name
        self.agent = agent
        self.env = env
        self.results = {}
        self.results_dir = os.path.join("./results", self.name, f"{self.env.parser.name}_{self.agent.name}_{self.agent.model.name}")
        os.makedirs(self.results_dir, exist_ok=True)

    @abc.abstractmethod
    def run(self):
        """Runs the Test."""
        pass

    def save_results(self):
        # Save overall results to results.json in results directory
        results_file = os.path.join(self.results_dir, "results.json")
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)

    def _format_action_text(self, action) -> str:
        if action is None:
            return ""
        if isinstance(action, str):
            return action.strip()
        try:
            return json.dumps(action, ensure_ascii=False)
        except TypeError:
            return str(action)

    def _annotate_action_on_screenshot(self, image, action):
        annotated = image.copy()
        if not action:
            return annotated

        draw = ImageDraw.Draw(annotated)
        bounds = self._extract_bounds(action)
        if bounds:
            draw.rectangle(bounds, outline=(255, 0, 0), width=5)

        action_text = self._format_action_text(action)
        if not action_text:
            return annotated

        font = ImageFont.load_default()
        wrap_width = max(20, annotated.width // 18)
        wrapped_lines = []
        for paragraph in action_text.splitlines() or [""]:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            wrapped_lines.extend(textwrap.wrap(paragraph, width=wrap_width) or [""])

        if not wrapped_lines:
            wrapped_lines = [action_text]

        _, top, _, bottom = draw.textbbox((0, 0), "Ag", font=font)
        line_height = bottom - top
        spacing = 6
        total_height = len(wrapped_lines) * (line_height + spacing) - spacing
        current_y = (annotated.height - total_height) / 2

        for line in wrapped_lines:
            text_width = draw.textlength(line, font=font)
            current_x = (annotated.width - text_width) / 2
            draw.text((current_x, current_y), line, font=font, fill=(255, 0, 0))
            current_y += line_height + spacing

        return annotated

    def _extract_bounds(self, action):
        bounds = action.get("bounds")
        if bounds is None and isinstance(action.get("params"), dict):
            bounds = action["params"].get("bounds")

        if not bounds:
            return None

        if isinstance(bounds, (list, tuple)) and len(bounds) >= 4:
            nums = bounds[:4]
        elif isinstance(bounds, str):
            import re
            nums = [int(num) for num in re.findall(r"-?\d+", bounds)]
        else:
            return None

        if len(nums) < 4:
            return None

        x1, y1, x2, y2 = nums[:4]
        if x1 == x2 and y1 == y2:
            return None
        return [x1, y1, x2, y2]
