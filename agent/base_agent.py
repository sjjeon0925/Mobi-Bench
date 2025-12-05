import abc
import dataclasses
from dataclasses import asdict
from environment.base_env import Env
from model.base_model import Model
from PIL import Image, ImageDraw
from typing import Any, Optional


HISTORY_PROMPT_TEMPLATE_BEFORE_CLICK = (
    'You are a click summarizer that summarizes the click event on the mobile phone screen. Given the user goal, previous event history, and the current screen marked with red cross indicating the click position, you will summarize the click event.\n\n'
    'The (overall) user goal/request is:{goal}\n\n'
    'Here is the history of previous summarizations:\n{history}\n\n'
    'Now I want you to summerize the click event performed on this screenshot image.\n\n'

    'This summary will be added to history and used for user guidance, so try to include essential information you think that will be most useful for understanding the overall execution of the goal. '
    'Maintain the format of the history and use the same structure for the new summary. '
    'Here is specific format for the summary:\n{format}\n'
    'Respond only the summary, do not include any other text.\n\n'
    'Summary of this click event: '
)

HISTORY_PROMPT_TEMPLATE_AFTER_CLICK = (
    'You are a click summarizer that summarizes the click event on the mobile phone screen. Given the user goal, previous event history, screenshot image before the click event, marked with red cross indicating the click position, and the screenshot image after the click event, you will summarize the click event.\n\n'
    'The (overall) user goal/request is:{goal}\n\n'
    'Here is the history of previous summarizations:\n{history}\n\n'
    'Now by comparing the two screenshots images before and after the click event and the click location, give a brief summary of the click event.\n\n'

    'This summary will be added to history and used for user guidance, so try to include essential information you think that will be most useful for understanding the overall execution of the goal. '
    'Maintain the format of the history and use the same structure for the new summary. '
    'Here is specific format for the summary:\n{format}\n'
    'Respond only the summary, do not include any other text.\n\n'
    'Summary of this click event: '
)


@dataclasses.dataclass()
class AgentInteractionData:
    instruction: str
    screen: str
    reason: str
    action: dict
    prompt: Optional[str] = None
    screenshot: Optional[Image.Image] = None
    retry_count: int = 0

    def to_dict(self):
        return asdict(self)

@dataclasses.dataclass()
class AgentInteractionResult:
    """Result of a single agent interaction with the environment.

    Attributes:
    done: Whether the agent indicates the entire session is done; i.e. this is
        the last interaction with the environment and the session will terminate.
    data: Environment and agent data from interaction.
    """
    done: bool
    success: bool
    data: AgentInteractionData

    def to_dict(self):
        dict = asdict(self)
        dict["data"] = self.data.to_dict()
        return dict



class Agent(abc.ABC):
    def __init__(self, model: Model, env: Env, name: str):
        self.model: Model = model
        self.name: str = name
        self.env: Env = env
        self.instruction: str = ""

    def reset(self, instruction: str):
        self.instruction = instruction

    @abc.abstractmethod
    def step(self) -> AgentInteractionResult:
        """Performs a step of the agent on the environment.

        Returns:
        AgentInteractionResult
        """
    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    def gen_click_history(self, goal: str, history: list[str], format: str, bounds: str, screenshot_before: Image.Image, screenshot_after: Image.Image = None) -> str:
        coords = bounds.replace('][', ',').strip('[]').split(',')
        x1, y1, x2, y2 = map(int, coords)
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2

        # Create copies before drawing
        screenshot_before_copy = screenshot_before.copy()
        
        # Draw a red cross at the clicked position
        draw = ImageDraw.Draw(screenshot_before_copy)
        draw.line([(center_x - 15, center_y), (center_x + 15, center_y)], fill="red", width=5)
        draw.line([(center_x, center_y - 15), (center_x, center_y + 15)], fill="red", width=5)
        screenshot_before_copy = self._add_labels(screenshot_before_copy, "Before Click (Click location is marked with red cross)")
        # Save the labeled screenshot showing click location
        screenshot_before_copy.save("click_location.png")

        history_str = '\n'.join([f'{i+1}. {event}' for i, event in enumerate(history)])
        if screenshot_after:
            screenshot_after_copy = screenshot_after.copy()
            screenshot_after_copy = self._add_labels(screenshot_after_copy, "After Click")
            prompt = HISTORY_PROMPT_TEMPLATE_AFTER_CLICK.format(goal=goal, history=history_str, format=format)
            raw_response = self.model.query_mm(prompt,
                                           [screenshot_before_copy, screenshot_after_copy]
                                           )
        else:
            prompt = HISTORY_PROMPT_TEMPLATE_BEFORE_CLICK.format(goal=goal, history=history_str, format=format)
            raw_response = self.model.query_mm(prompt,
                                           [screenshot_before_copy]
                                           )
        return raw_response



    def _add_labels(self, image: Image.Image, label: str):
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(image)

        # Use default font with size 24
        font = ImageFont.load_default().font_variant(size=24)

        # Draw text centered at top
        text_width = draw.textlength(label, font=font)
        x = (image.width - text_width) / 2
        draw.text((x, 20), label, fill='red', font=font)

        return image
