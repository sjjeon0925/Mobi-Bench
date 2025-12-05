def _action_selection_prompt(goal: str, history: list[str], screen: str, additional_guidelines: list[str] = None, mm: bool = False) -> str:
    """
    Construct the action selection prompt for a text-only model, VisionTasker style in English.

    Args:
        goal: User's instruction.
        history: List of previous action summaries.
        screen: Description of current UI elements.
        additional_guidelines: Optional extra guidelines.

    Returns:
        A full prompt string formatted for LLM input.
    """
    history_str = ''
    if history:
        tapped_str = ''.join(history)
        history_str = f', actions performed so far: {tapped_str}'

    guideline_str = ''
    if additional_guidelines:
        guideline_str = '\n'.join(additional_guidelines)

    prompt = (
        f"Q: {goal}{history_str}. "
        f"The current screen contains the following UI elements: {screen}\n"
    )
    if guideline_str:
        prompt += f"\n{guideline_str}\n"

    prompt += (
        '\nNow decide the next action.\n'
        'Respond using the following format:\n'
        '{\n'
        '  "Reason": "<brief reasoning of your decision>",\n'
        '  "Action": {{ "action_type": "<click/long_click/input/scroll/finish/navigate_back>", "index": <int or null>, "params": {{...}} }}\n'
        '  "Screen resolution: (...,...)" example: "Screen resolution: (1080, 2400)"\n'
        '}\n'
    )
    return prompt


def _summarize_prompt(goal: str, action: str, reason: str, before_screen: str, after_screen: str, mm: bool = False) -> str:
    """
    Generate a one-sentence summary prompt for the action.

    Args:
        goal: Overall user goal.
        action: Action that was taken.
        reason: Reason why that action was taken.
        before_screen: Description before the action.
        after_screen: Description after the action.

    Returns:
        Prompt string asking for a summary.
    """
    return (
        f"User goal: {goal}\n"
        f"Before the action, the screen showed: {before_screen}\n"
        f"Action taken: {action}\n"
        f"Reason: {reason}\n"
        f"After the action, the screen shows: {after_screen}\n\n"
        "Summarize this step in a single sentence:"
    )