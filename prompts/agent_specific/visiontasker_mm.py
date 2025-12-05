def _action_selection_prompt(
        goal: str,
        history: list[str],
        screen: str,
        additional_guidelines: list[str] | None = None,
        mm: bool = True
) -> str:
    """Prompt for action selection with multimodal input (VisionTasker style)."""
    prefix = (
        "You are an intelligent mobile assistant. Your job is to help the user complete the task by operating the smartphone UI.\n"
        "You are provided with:\n"
        "- A user instruction.\n"
        "- A sequence of previously executed actions (summarized).\n"
        "- A screenshot of the current UI (attached separately).\n"
        "- A text description of the current UI elements.\n\n"
        "Now, select the next most reasonable action to move toward completing the task.\n\n"
    )

    history_str = '\n'.join(history) if history else 'None'
    guidelines_str = ''
    if additional_guidelines:
        guidelines_str = 'Additional guidelines:\n' + '\n'.join(f'- {g}' for g in additional_guidelines) + '\n\n'

    prompt = (
            prefix +
            f"User Task:\n{goal}\n\n"
            f"{guidelines_str}"
            f"Previous Action Summaries:\n{history_str}\n\n"
            f"Current UI Description:\n{screen}\n\n"
            "Respond in the following JSON format only:\n"
            '{{\n'
            '  "Reason": "<brief reasoning of your decision>",\n'
            '  "Action": {{ "action_type": "<click/long_click/input/scroll/finish/navigate_back>", "index": <int or null>, "params": {{...}} }}\n'
            '}}\n'
    )
    return prompt


def _summarize_prompt(
        goal: str,
        action: str,
        reason: str,
        before_screen: str,
        after_screen: str,
        mm: bool = True
) -> str:
    """Prompt for summarizing a single UI action step (VisionTasker style)."""
    prompt = (
        "You are an assistant summarizing a UI action step for a mobile task.\n"
        "You are given the following information:\n"
        f"- User Task: {goal}\n"
        f"- Action Taken: {action}\n"
        f"- Reason: {reason}\n"
        "- Description of the screen *before* the action:\n"
        f"{before_screen}\n"
        "- Description of the screen *after* the action:\n"
        f"{after_screen}\n\n"
        "Summarize what was attempted and whether the UI changed as expected. "
        "Your summary should help inform future decisions and track task progress. "
        "It should be one sentence.\n\n"
        "Summary: "
    )
    return prompt