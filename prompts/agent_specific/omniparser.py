def _action_selection_prompt(
        goal: str,
        history: list[str],
        screen: str,
        additional_guidelines: list[str] = None,
        mm: bool = True
) -> str:
    """
    Action selection prompt for OmniParser (multimodal only).

    Args:
        goal: User's instruction string.
        history: List of previous step summaries.
        screen: Structured UI annotations (OCR + caption).
        additional_guidelines: Optional task-specific hints.

    Returns:
        Prompt string to feed into VLM.
    """
    prefix = (
        "You are an intelligent assistant. Your job is to help the user complete the task "
        "by interacting with a mobile app UI. You are provided with the following:\n"
        "- A user instruction.\n"
        "- A list of previously summarized actions.\n"
        "- An annotated image of the current screen (provided separately).\n"
        "- A list of structured UI elements detected on the current screen.\n\n"
        "Select the most reasonable next action that helps complete the task."
    )

    history_str = '\n'.join(history) if history else 'None'
    guideline_str = ""
    if additional_guidelines:
        guideline_str = "\nAdditional Guidelines:\n" + '\n'.join(f"- {g}" for g in additional_guidelines)

    prompt = (
        f"{prefix}\n\n"
        f"User Instruction:\n{goal}\n\n"
        f"{guideline_str}\n"
        f"Previously Summarized Actions:\n{history_str}\n\n"
        f"Current UI Elements:\n{screen}\n\n"
        "Respond strictly in the following JSON format:\n"
        "{{\n"
        '  "Reason": "<brief explanation>",\n'
        '  "Action": {\n'
        '    "action_type": "<click/input/scroll/finish/navigate_back>",\n'
        '    "index": <int>,\n'
        '    "params": {...}\n'
        "  }\n"
        "}}\n"
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
    """
    Step summarization prompt for OmniParser (multimodal only).

    Args:
        goal: User's overall goal.
        action: Executed action (json string).
        reason: Reasoning for the action.
        before_screen: UI description before the action.
        after_screen: UI description after the action.

    Returns:
        Prompt string requesting a one-sentence summary.
    """
    return (
        "You are summarizing a UI action step for an intelligent assistant.\n"
        "Below is the relevant information for this step:\n\n"
        f"User Instruction: {goal}\n"
        f"Action Taken: {action}\n"
        f"Reason: {reason}\n"
        "UI Description Before Action:\n"
        f"{before_screen}\n"
        "UI Description After Action:\n"
        f"{after_screen}\n\n"
        "Summarize this action in one sentence:"
    )