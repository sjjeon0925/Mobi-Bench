import string
from typing import Any
VALID_ACTIONS = {
    "click",
    "finish",
    "long_click",
    "input",
    "navigate_back",
    "scroll",
  "open_app",
}
ACTIONS_WITHOUT_ELEMENT = {
    "finish",
    "navigate_back",
  "open_app",
}
ACTIONS_WITH_VALUE = {"input", "scroll"}


SEEACT_PROMPT_PREFIX = """Imagine that you are imitating humans operating an Android device for a task step by step. At each stage, you can see the Android screen like humans by a screenshot and know the previous actions before the current step decided by yourself through recorded history. You need to decide on the first following action to take. You can tap on an element, long-press an element, swipe, input text, open an app, or use the keyboard enter, home, or back key. Unlike humans, for typing (e.g., in text areas, text boxes), you should try directly typing the input or selecting the choice, bypassing the need for an initial click. You should not attempt to create accounts, log in or do the final submission. Terminate when you deem the task complete or if it requires potentially harmful actions."""

SEEACT_PROMPT_GUIDELINE = """The screenshot below shows the Android screen you see. Follow the following guidance to think step by step before outlining the next action step at the current stage:

(Current Screen Identification)
Firstly, think about what the current screen is.

(Previous Action Analysis)
Secondly, combined with the screenshot, analyze each step of the previous action history and their intention one by one. Particularly, pay more attention to the last step, which may be more related to what you should do now as the next step. Specifically, if the last action involved an INPUT TEXT, always evaluate whether it necessitates a confirmation step, because typically a single INPUT TEXT action does not make effect (often, simply pressing 'Enter', assuming the default element involved in the last action, unless other clear elements are present for interaction).

(Screenshot Details Analysis)
Closely examine the screenshot to check the status of every part of the screen to understand what you can operate with and what has been set or completed. You should closely examine the screenshot details to see what steps have been completed by previous actions even though you are given the textual previous actions. Because the textual history may not clearly and sufficiently record some effects of previous actions, you should closely evaluate the status of every part of the screen to understand what you have done.

(Next Action Based on Android screen and Analysis)
Then, based on your analysis, in conjunction with human phone operation habits and the logic of app design, decide on the following action. Describe the high-level target on the Android screen and what you intend to do next without specifying taps/bounds yet.

To be successful, it is important to follow the following rules:
1. You should only issue a valid action given the current observation.
2. You should only issue one action at a time
3. For handling the select dropdown elements on a screen, it's not necessary for you to provide completely accurate options right now. The full list of options for these elements will be supplied later.
4. If the target app is not open (home/launcher/blank screen), your very next action must be `open_app` with the exact app name. Do NOT swipe the app drawer or tap icons to find it; always call `open_app` to launch the app first."""


SEEACT_CHOICE_PROMPT_DICT = {
    "prefix": SEEACT_PROMPT_PREFIX,
    "guideline": SEEACT_PROMPT_GUIDELINE,
    "action_selection": """(Reiteration)
First, reiterate your next target element and the corresponding action at a high level.

(Multichoice Question)
Below is a multi-choice question, where the choices are elements on the screen. All elements are arranged in the order based on their height on the screen, from top to bottom (and from left to right). This arrangement can be used to locate them. From the screenshot, find out where and what each one is on the screen, taking into account both their text content and details. Then, determine whether one matches your target element. Please examine the choices one by one. Choose the matching one. If multiple options match your answer, choose the most likely one by re-examining the screenshot, the choices, and your further reasoning. If you would like to perform a swipe action, you can optionally select the choice where you will swipe.""",
    
  "response_format": """(Final Answer)
Finally, conclude your answer using the format below. Ensure your answer is strictly adhering to the format provided below. Please do not leave any explanation in your answers of the final standardized format part, and this final part should be clear and certain. The element choice, action, and value should be in three separate lines.
'action example list:\n'
    '- Click/tap on a UI element (specified by its index) on the screen:'
    ' `{{"action_type": "click", "index": <target_UI_id>}}`.'
    '- Long click on a UI element (specified by its index) on the screen:'
    ' `{{"action_type": "long_click", "index": <target_UI_id>}}`.'
    '- Type text into keyboard, this action contains clicking the text field, typing in the text and pressing the enter, so no need to click on the target field to start:'
    ' `{{"action_type": "input", "text": <text_input>, "index": <target_UI_id>}}`'
    '- Scroll the screen in one of the four directions:'
    ' `{{"action_type": "scroll", "direction": <up, down, left, right>}}`'
    '- Navigate back to the previous screen: `{{"action_type": "navigate_back"}}`'
    '- Open an app (if installed): `{{"action_type": "open_app", "params": {{"app": <app_name>}}}}`
    '  Never swipe or tap around to find the app icon; always call `open_app` with the exact app name when you need to launch an app.'
    '  If no target app is open yet (home/launcher/blank), your first step must be `open_app` for the required app.'
    '- Finish the task with status complete: `{{"action_type": "finish", "status": "complete"}}`\n'
    """
    + 'Do not include any additional text or explanation in your answer.\n'
    + 'Be sure to follow the format strictly. Especially, do not use double braces "{{" or "}}" in your answer.\n'
    + 'You should use single braces "{" and "}" in your answer.\n'
    + 'Format:\n'
    + 'example: {"action_type":...}\n'
    + '\nYour Answer:\n'
}

def generate_action_generation_prompt(
    task: str,
    guideline: str,
    previous_actions: list[str] | None = None,
) -> str:
    """Generate the first phase prompt for the SeeAct experiment setup.

    It focuses on the task description, previous actions and a question
    description without disruption from formatting or referring prompts.

    Args:
        task: The task description.
        question_description: A description of the question or task at hand.
        previous_actions: A list of previous actions taken.

    Returns:
        list: A list containing the system role and the generated query text.
    """
    query_text = "You are asked to complete the following task: " + task + "\n\n"
    previous_action_text = "Previous Actions:\n"
    if previous_actions is None:
        previous_actions = []
    for i, action_text in enumerate(previous_actions):
        previous_action_text += f"{i+1}. {action_text}\n"
    query_text += previous_action_text + "\n" + guideline
    return query_text

def generate_grounding_prompt(
    action_selection: str = "",
    response_format: str = "",
    ui_element_choices: list[str] | None = None,
) -> str:
  """Generate a referring prompt that includes the element format, action format, and value format along with choices, if applicable, for the SeeAct experiment setup.

  Args:
      referring_description: Description on how to format the output.
      element_format: The format for specifying the element.
      ui_element_choices: A list of choices for the next action.

  Returns:
      The generated referring prompt.
  """
  action_selection = (
      action_selection + "\n\n" if action_selection else ""
  )

  if ui_element_choices:
    choice_text = ui_element_choices
    action_selection += choice_text

  action_selection += f"{response_format}"

  return action_selection

def generate_multiple_choice(index: int) -> str:
  """Generate an option name based on the index.

  Args:
    index: The index of the option.

  Returns:
    The generated option name.
  """
  if index > 26 * 26:
    raise ValueError(f"Index {index} is greater than 26 * 26")

  if index < 26:
    return string.ascii_uppercase[index]
  else:
    first_letter_index = (index - 26) // 26
    second_letter_index = (index - 26) % 26
    first_letter = string.ascii_uppercase[first_letter_index]
    second_letter = string.ascii_uppercase[second_letter_index]
    return f"{first_letter}{second_letter}"
  
def format_action_options(choices: list[str]) -> str:
  """Format the given choices into a structured option text for presentation in the prompt.

  Args:
    choices: A list of choices to be formatted.

  Returns:
    The formatted choices text.
  """
  option_text = ""
  for idx, choice in enumerate(choices):
    option_name = idx
    option_text += f"{option_name}. {choice}\n"

  option_text += (
      "If none of these elements match your target element, please select"
      f" {len(choices)}. None of the other options match the correct element.\n\n"
  )

  return option_text

def generate_seeact_prompts(
    task: str,
    previous_actions: list[str] | None = None,
    ui_element_choices: list[Any] | None = None
) -> tuple[str, str]:
  """Generates prompts for the SeeAct setup.

  Args:
      task: Description of the task to be performed.
      previous_actions: A list of actions previously taken.
      ui_element_choices: A list of choices available for the next action,
        derived from the accessibility tree.

  Returns:
      A list of strings forming the complete prompt for the SeeAct task.
  """
  prefix = SEEACT_CHOICE_PROMPT_DICT["prefix"]
  guideline = SEEACT_CHOICE_PROMPT_DICT["guideline"]
  action_selection = SEEACT_CHOICE_PROMPT_DICT["action_selection"]
  response_format = SEEACT_CHOICE_PROMPT_DICT["response_format"]
  action_generation_prompt = prefix + "\n" + generate_action_generation_prompt(
      task,
      guideline,
      previous_actions=previous_actions,
  )


  return (
    action_generation_prompt,
    generate_grounding_prompt(
        action_selection=action_selection,
        response_format=response_format,
        ui_element_choices=ui_element_choices,
    ),
  )
