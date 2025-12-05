import json

PROMPT_PREFIX = (
    'You are an agent who can operate an Android phone on behalf of a user.'
    ' Based on the goal and the current screen, you must pick exactly one action'
    ' from the list below and respond in JSON.\n\n'
    'When given a user request, you will try to complete it step by step.'
    ' At each step, you will be given the current screenshot (including the'
    ' original screenshot and the same screenshot with bounding'
    ' boxes and numeric indexes added to some UI elements) and a history of'
    ' what you have done (in text). Based on these pieces of information and'
    ' the goal, choose one action in the correct JSON format.\n'
    '- If you think the task has been completed:'
    ' `{{"action_type": "finish", "status": "complete"}}`\n'
    '- Click/tap on an element using its numeric index:'
    ' `{{"action_type": "click", "index": <target_index>}}`\n'
    '- Long press on an element using its numeric index:'
    ' `{{"action_type": "long_click", "index": <target_index>}}`\n'
    '- Type text into a field (includes focusing and submitting):'
    ' `{{"action_type": "input", "index": <target_index>, "params": {{"text": "<text_input>"}}}}`\n'
    '- Scroll the screen or a scrollable element:'
    ' `{{"action_type": "scroll", "direction": <up, down, left, right>, "index": <optional_target_index>}}`\n'
    '- Navigate back: `{{"action_type": "navigate_back"}}`\n'
    '- Open an app (no-op if not installed):'
    ' `{{"action_type": "open_app", "params": {{"app": "<name>"}}}}`\n'
)

GUIDANCE = (
    'Here are some useful guidelines you need to follow:\n'
    '- If the desired state is already achieved, you can complete the task with `finish`.\n'
    '- Use `open_app` to launch apps; do not hunt for icons by tapping/scrolling unless unavoidable.\n'
    '- For typing, always use `input` with `params.text` instead of tapping keys one by one. Delete any default text first if needed.\n'
    '- For `click`/`long_click`/`input`, the index must be visible in the screenshot/UI list; ignore hidden elements.\n'
    '- If you cannot find content, try `scroll` in the appropriate direction; if one direction fails, try the opposite.\n'
    '- Keep actions minimal and goal-directed; if something fails repeatedly, switch strategy rather than repeating blindly.\n'
)


ACTION_SELECTION_PROMPT_TEMPLATE = (
    PROMPT_PREFIX
    + '\nThe current user goal/request is: {goal}\n\n'
    'Here is a history of what you have done so far:\n{history}\n\n'
    'The current screenshot and the same screenshot with bounding boxes'
    ' and labels added are also given to you.\n'
    'Here is a list of detailed'
    ' information for some of the UI elements (notice that some elements in'
    ' this list may not be visible in the current screen and so you can not'
    ' interact with it, can try to scroll the screen to reveal it first),'
    ' the numeric indexes are'
    ' consistent with the ones in the labeled screenshot:\n{ui_elements}\n'
    + GUIDANCE
    + '{additional_guidelines}'
    + '\nNow output an action from the above list in the correct JSON format.'
    ' Your answer must be a single JSON object with "Reason" and "Action" fields, like:\n'
    ' {{"Reason": "...", "Action": {{"action_type": "...", "index": <UI index or null>, "params": {{...}} }} }}\n\n'
    'Your Answer:\n'
)


SUMMARY_PROMPT_TEMPLATE = (
    PROMPT_PREFIX
    + '\nThe (overall) user goal/request is: {goal}\n'
    'Now I want you to summerize the latest step.\n'
    'You will be given the screenshot before you performed the action (which'
    ' has a text label "before" on the bottom right), the action you chose'
    ' (together with the reason) and the screenshot after the action was'
    ' performed (which has a text label "after" on the bottom right).\n'
    'Also here is the list of detailed information for some UI elements'
    ' in the before screenshot:\n{before_elements}\n'
    'Here is the list for the after screenshot:\n{after_elements}\n'
    'This is the action you picked: {action}\n'
    'Based on the reason: {reason}\n\n'
    'By comparing the two screenshots (plus the UI element lists) and the'
    ' action performed, give a brief summary of this step. This summary'
    ' will be added to action history and used in future action selection,'
    ' so try to include essential information you think that will be most'
    ' useful for future action selections like what you'
    ' intended to do, why, if it worked as expected, if not'
    ' what might be the reason (be critical, the action/reason might be'
    ' wrong), what should/should not be done next and so on. Some more'
    ' rules/tips you should follow:\n'
    '- Keep it short (better less than 50 words) and in a single line\n'
    "- Some actions (like `answer`, `wait`) don't involve screen change,"
    ' you can just assume they work as expected.\n'
    '- Given this summary will be added into action history, it can be used as'
    ' memory to include information that needs to be remembered, or shared'
    ' between different apps.\n\n'
    'Summary of this step: '
)


def _action_selection_prompt(
    goal: str,
    history: list[str],
    ui_elements_description: str,
    additional_guidelines: list[str] | None = None,
    mm: bool = False,
    isxml: bool = True,
    prompt_type: str = "react",
) -> str:
    hist_text = ""
    for i, action_text in enumerate(history):
        hist_text += f"{action_text}\n"

    extra_guidelines = ""
    if additional_guidelines:
        extra_guidelines = "For The Current Task:\n"
        for guideline in additional_guidelines:
            extra_guidelines += f"- {guideline}\n"

    ui_text = ui_elements_description if ui_elements_description else "Not available"
    return ACTION_SELECTION_PROMPT_TEMPLATE.format(
        goal=goal,
        history=hist_text,
        ui_elements=ui_text,
        additional_guidelines=extra_guidelines,
    )


def _summarize_prompt(
    goal: str,
    action: str,
    reason: str,
    before_elements: str,
    after_elements: str,
    mm: bool = False,
    isxml: bool = True,
    summary_type: str = "post",
):
    action_obj = json.loads(action) if isinstance(action, str) else action
    return SUMMARY_PROMPT_TEMPLATE.format(
        goal=goal,
        before_elements=before_elements if before_elements else "Not available",
        after_elements=after_elements if after_elements else "Not available",
        action=action_obj,
        reason=reason,
    )
