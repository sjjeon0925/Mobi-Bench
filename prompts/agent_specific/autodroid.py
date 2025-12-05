import json


PROMPT_PREFIX = (
    "You are a smartphone assistant to help users complete tasks by interacting with mobile apps. "
    "Given a task, the previous UI actions, and the content of current UI state, "
    "your job is to decide whether the task is already finished by the previous actions, and if not, decide which UI element in current UI state should be interacted."
)

ACTION_SELECTION_PROMPT_TEMPLATE = (
        PROMPT_PREFIX
        + '\nTask: {goal}\n\n'
        + 'Previous UI actions:\n{history}\n\n'
        + 'Current UI state (Each UI element is annotated in the screenshot with its index number): \n{screen}\n\n'
        + "Your answer should always use the following format: "
        + "{{ \"Steps\": \"...<steps usually involved to complete the above task on a smartphone>\", "
        + "\"Analyses\": \"...<Analyses of the relations between the task, and relations between the previous UI actions and current UI state>\", "
        + "\"Finished\": \"Yes/No\", "
        + "\"Next step\": \"None or a <high level description of the next step>\", "
        + "\"index\": \"an integer or -1 (if the task has been completed by previous UI actions)\", "
        + "\"action\": \"click or long_click or input or scroll or finish or navigate_back\", "
        + "\"scroll_direction\": \"up or down or left or right\", "
        + "\"input\": \"N/A or ...<input text>\" }} \n\n"
        + "\""
        + "**Note that the index is the index number of the UI element to interact with. "
        + "If you think the task has been completed by previous UI actions, the id should be -1. "
        + "If 'Finished' is 'Yes', then the 'description' of 'Next step' is 'None', otherwise it is a high level description of the next step. "
        + "If the 'action' is 'click' or 'long-click', the 'input_text' and 'scroll_direction'is N/A. "
        + "If action is input, 'input_text' is the text that you want to input, and the 'scroll_direction' is N/A. "
        + "If the action is 'scroll', 'scroll_direction' is the direction of the scroll, and the 'input_text' is N/A. "
        + "Please do not output any content other than the JSON format. **"
)

def _action_selection_prompt(
        goal: str,
        history: list[str],
        screen: str,
) -> str:
    if history:
        history_str = '\n'.join(f"{i+1}. {json.dumps(step)}" for i, step in enumerate(history))
    else:
        history_str = ''

    return ACTION_SELECTION_PROMPT_TEMPLATE.format(
        goal=goal,
        history=history_str,
        screen=screen,
    )