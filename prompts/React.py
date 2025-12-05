import json

IMAGE_ONLY_ACTION_GUIDELINES = (
    'action example list:\n'
    '- Click/tap on a location on the screen:\n'
    ' `{{"action_type": "click", "coordinates": [<y>, <x>]}}` where y and x are float values between 0.0 and 1.0 representing the vertical and horizontal position respectively. The top-left corner is [0.0, 0.0] and the bottom-right is [1.0, 1.0]. Always give precise decimal values (e.g., 0.3700, 0.8200), not rough 0/1, so the position can be accurately rescaled to different screenshot sizes.\n\n'
    '- Type text into a field at a specific location:\n'
    ' `{{"action_type": "input", "coordinates": [<y>, <x>], "params": {{"text": "<text_to_type>"}}}}` where y and x are the normalized coordinates of the target input field. Use precise decimals (e.g., 4 decimal places) so the target field can be correctly located after rescaling.\n\n'
    '- Scroll the current screen:\n'
    ' `{{"action_type": "scroll", "direction": <up, down, left, right>}}`.\n\n'
    '- Navigate back:\n'
    ' `{{"action_type": "navigate_back"}}`.\n\n'
    '- Open an app (if installed):\n'
    ' `{{"action_type": "open_app", "params": {{"app": <app_name>}}}}`.\n\n'
    '- Finish the task:\n'
    ' `{{"action_type": "finish", "status": "complete"}}`.\n'
)

ACTION_GUIDELINES = (
    'action example list:\n'
    '- Click/tap on a UI element (specified by its index) on the screen:\n'
    ' `{{"action_type": "click", "index": <target_UI_index>}}`.\n'
    '  Use only when the element is already visible and unambiguous. The click should immediately trigger the next UI change (open a page, toggle a control, confirm a dialog). Do not click blindly—identify the correct index from the UI descriptions and Do not forget to cite that index in the JSON.\n\n'
    '- Type text:\n'
    ' `{{"action_type": "input", "index": <target_UI_index>, "params": {{"text": "<text_input>"}}}}`.\n'
    '  Use only when the goal explicitly requires entering text into the focused field (search, login, chat input). Do not combine with manual clicks on the keyboard; describe the exact text you will enter and always wrap it in `params.text`. Do not forget to include the correct index as well.\n\n'
    '- Scroll the current screen or list:\n'
    ' `{{"action_type": "scroll", "direction": <up, down, left, right>}}`.\n'
    '  Use when the element you need is off-screen or more content needs to be revealed. Choose the direction that moves toward the target (e.g., `down` to reveal lower content). Do not over-scroll; perform one scroll per action.\n\n'
    '- Navigate back:\n'
    ' `{{"action_type": "navigate_back"}}`.\n'
    '  Use when the current screen is a dead end, you opened the wrong page, or the goal requires returning to the previous view. Do not use `click` on on-screen back buttons unless the instruction explicitly calls for that specific UI button.\n\n'
    '- Open an app (if installed):\n'
    ' `{{"action_type": "open_app", "params": {{"app": <app_name>}}}}`.\n'
    '  Use at the start of a task or whenever you must switch apps. Do not scroll the home screen or tap icons manually to find an app—always issue `open_app` with the app name and let the system launch it. If the app name is given in the goal, copy it exactly.\n\n'
    '- Finish the task:\n'
    ' `{{"action_type": "finish", "status": "complete"}}`.\n'
    '  Only use after verifying every requirement in the goal has been satisfied. Once the task is complete, choose `finish` immediately instead of taking additional exploratory actions.\n'
)

PROMPT_PREFIX_VERIFICATION = (
    'You are an agent capable of operating an Android phone on behalf of a user.\n\n'
    'The current step is to verify the action you performed. Based on the resources provided, determine whether the action you decided to take to achieve your GOAL was correct. The process of how you decided on this action will be explained to you.:\n\n'
    'Tasks described in the request/goal are executed step by step, progressing through actions on the phone. When a user request is given, you attempt to complete the task step by step. At each step, a list of descriptions for most UI elements on the current screen will be provided (each element can be specified by an index). Additionally, the history of actions you previously performed will also be provided. Based on this information and the goal, you must select one of the tasks from the following list (including action descriptions and JSON format) and output the selected task in the correct JSON format.\n\n'
) + ACTION_GUIDELINES

PROMPT_PREFIX_SUMMARIZE = (
    'You are an agent capable of operating an Android phone on behalf of a user.\n\n'
    'The current step is summarize the action you performed. Based on the resources provided, summarize the action you decided. The process of how you decided on this action will be explained to you.:\n\n'
    'Tasks described in the request/goal are executed step by step, progressing through actions on the phone. When a user request is given, you attempt to complete the task step by step. At each step, a list of descriptions for most UI elements on the current screen will be provided (each element can be specified by an index). Additionally, the history of actions you previously performed will also be provided. Based on this information and the goal, you must select one of the tasks from the following list (including action descriptions and JSON format) and output the selected task in the correct JSON format.\n\n'
) + ACTION_GUIDELINES

PROMPT_PREFIX_VERIFICATION_HISTORY = (
    'You are an agent capable of operating an Android phone on behalf of a user.\n\n'
    'The current step is to verify the action history you performed. Based on the resources provided, determine whether the action history you decided to take to achieve your GOAL was correct. The process of how you decided on this action will be explained to you.:\n\n'
    'Tasks described in the request/goal are executed step by step, progressing through actions on the phone. When a user request is given, you attempt to complete the task step by step. At each step, a list of descriptions for most UI elements on the current screen will be provided (each element can be specified by an index). Additionally, the history of actions you previously performed will also be provided. Based on this information and the goal, you must select one of the tasks from the following list (including action descriptions and JSON format) and output the selected task in the correct JSON format.\n\n'
) + ACTION_GUIDELINES

PROMPT_PREFIX_WITH_XML = (
    'You are an agent who can operate an Android phone on behalf of a user.'
    " Based on user's goal/request, you may\n"
    '- Complete some tasks described in the requests/goals by performing'
    ' actions (step by step) on the phone.\n\n'
    'When given a user request, you will try to complete it step by step. At'
    ' each step, a list of descriptions for most UI elements on the'
    ' current screen will be given to you if possible (each element can be specified by an'
    ' index), together with a history of what you have done in previous steps.'
    ' Based on these pieces of information and the goal, you must choose to'
    ' perform one of the action in the following list (action description'
    ' followed by the JSON format) by outputing the action in the correct JSON'
    ' format.\n'
) + ACTION_GUIDELINES

PROMPT_PREFIX_WITHOUT_XML = (
    'You are an agent who can operate an Android phone on behalf of a user.'
    " Based on user's goal/request, you may\n"
    '- Complete some tasks described in the requests/goals by performing'
    ' actions (step by step) on the phone.\n\n'
    'When given a user request, you will try to complete it step by step. At'
    ' each step, a list of descriptions for most UI elements on the'
    ' current screen will be given to you (each element can be specified by an'
    ' index), together with a history of what you have done in previous steps.'
    ' Based on these pieces of information and the goal, you must choose to'
    ' perform one of the action in the following list (action description'
    ' followed by the JSON format) by outputing the action in the correct JSON'
    ' format.\n'
) + ACTION_GUIDELINES

IMAGE_ONLY_PROMPT_PREFIX = (
    'You are an agent who can operate an Android phone on behalf of a user by seeing the screen. '
    "Based on user's goal/request, you will perform actions on the phone. "
    'At each step, you will be given a screenshot of the current screen.'
    ' Based on the visual information and the goal, you must choose to'
    ' perform one of the action in the following list by outputing the action in the correct JSON'
    ' format.\n'
) + IMAGE_ONLY_ACTION_GUIDELINES

IMAGE_ONLY_ACTION_SELECTION_PROMPT_TEMPLATE = (
        '{prefix}'
        + '\nThe current user goal/request is: {goal}'
        + '\n\nHere is a history of what you have done so far:\n{history}'
        + '\n\nFirst, think step-by-step about what you see on the screen and how it relates to the user\'s goal. Second, formulate a plan to achieve the goal. Finally, based on your plan, choose the single best action to perform right now. Now look at the screen and output an action from the above list in the correct JSON format.'
        ' Your answer must be only the JSON object representing the action '
        + 'following the reason why you do that. Your answer should look like:\n'
        + 'Do not include any additional text or explanation in your answer.\n'
        + 'Do not use double brakets in your answer, just use single brackets.\n'
        + 'example: {{"Reason": "...","Action": {{"action_type":...}}}}\n\n'
        + 'Your Answer:\n'
)

IMAGE_ONLY_PURE_ACTION_SELECTION_PROMPT_TEMPLATE = (
        '{prefix}'
        + '\nThe current user goal/request is: {goal}'
        + '\n\nHere is a history of what you have done so far:\n{history}'
        + '\n\nFirst, think step-by-step about what you see on the screen and how it relates to the user\'s goal. Second, formulate a plan to achieve the goal. Finally, based on your plan, choose the single best action to perform right now. Now look at the screen and output an action from the above list in the correct JSON format.'
        ' Your answer must be only the JSON object representing the action.\n'
        + 'Do not include any additional text or explanation in your answer.\n'
        + 'Do not use double brakets in your answer, just use single brackets.\n'
        + 'example: {{"action_type":...}}\n\n'
        + 'Your Answer:\n'
)

REACT_ACTION_SELECTION_PROMPT_TEMPLATE= (
        '{prefix}'
        + '\nThe current user goal/request is: {goal}'
        + '\n\nHere is a history of what you have done so far:\n{history}'
        + '\n\nHere is a representation of UI elements on the current'
          ' screen:\n<screen>{ui_elements_description}</screen>\n\n'
        #+ GUIDANCE
        + '{additional_guidelines}'
        + '\n\nNow output an action from the above list in the correct JSON format.'
        ' Your answer must be only the JSON object representing the action '
        + 'following the reason why you do that. Your answer should look like:\n'
        + 'Do not include any additional text or explanation in your answer.\n'
        + 'Do not use double brakets in your answer, just use single brackets.\n'
        + 'example: {{"Reason": "...","Action": {{"action_type":...}}}}\n\n'
        + 'Your Answer:\n'
)

PURE_ACTION_SELECTION_PROMPT_TEMPLATE = (
    '{prefix}'
    + '\n{few_shot_example}'
    + '\nThe current user goal/request is: {goal}'
    + '\n\nHere is a history of what you have done so far:\n{history}'
    + '\n\nHere is a representation of UI elements on the current'
    ' screen:\n<screen>{ui_elements_description}</screen>\n\n'
    #+ GUIDANCE
    + '{additional_guidelines}'
    + '\n\nNow output an action from the above list directly in the correct JSON format.'
    ' Your answer must be only the JSON object representing the action.\n'
    + 'Do not include any additional text or explanation in your answer.\n'
    + 'Do not use double brakets in your answer, just use single brackets.\n'
    + 'example: {{"action_type":...}}\n\n'
    + '\nYour Answer:\n'
)

FEW_SHOT_ACTION_EXAMPLE = f"""
Here is a reference example showing how you should reason about one step and respond in JSON format. Review it to remind yourself of your role, then focus on the current screen and decide what to do next.
Example:
<screen>
<div bounds="[0,128][1080,2337]" index="0">
  <Button bounds="[0,128][1080,2337]" index="1" />
  <Button bounds="[0,128][1080,275]" index="2">
    <Button description="Show navigation drawer" bounds="[0,128][147,275]" index="3" />
  </Button>

  <ScrollView description="Home timeline list" scrollable="true" bounds="[0,275][1080,2337]" index="4">

    <Button long-clickable="true" bounds="[0,275][1080,1642]" index="5">
      <div description="Sophia Lee @SophiaLee989612.               2 minutes ago.     " bounds="[0,275][1080,1641]" index="6">
        <div bounds="[32,275][1080,1641]" index="7">
          <Button description="Profile image" bounds="[32,301][137,406]" index="8" />
          <div bounds="[163,280][1080,1641]" index="9">
            <Button bounds="[985,280][1069,364]" index="10" />
            <div bounds="[163,343][1048,1641]" index="11">
              <Button bounds="[163,361][1048,1536]" index="12">
                <Button description="Image" bounds="[163,361][1048,1536]" index="13" />
              </Button>
              <div bounds="[163,1536][1048][1641]" index="14">
                <Button bounds="[163,1536][338,1641]" index="15" />
                <Button bounds="[338,1536][539,1641]" index="16" />
                <Button bounds="[539,1536][740,1641]" index="17" />
                <Button bounds="[740,1536][941,1641]" index="18" />
                <Button bounds="[941,1536][1048,1641]" index="19" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </Button>

    <Button long-clickable="true" bounds="[0,1642][1080,2337]" index="20">
      <div description="Sophia Lee @SophiaLee989612.               2 days ago.     15 verified views. " bounds="[0,1642][1080,2337]" index="21">
        <div bounds="[32,1642][1080,2337]" index="22">
          <Button description="Profile image" bounds="[32,1668][137,1773]" index="23" />
          <div bounds="[163,1647][1080,2337]" index="24">
            <Button bounds="[985,1647][1069,1731]" index="25" />
            <Button bounds="[163,1728][1048,2337]" index="26">
              <Button description="Image" bounds="[163,1728][1048,2337]" index="27" />
            </Button>
          </div>
        </div>
      </div>
    </Button>

  </ScrollView>

  <div bounds="[668,1611][1080,2190]" index="28">
    <div bounds="[668,1611][1080,2106]" index="29">
      <TextField bounds="[668,1635][902,1713]" index="30">Spaces</TextField>
      <Button description="Start your Space" bounds="[902,1611][1027,1736]" index="31" />
      <TextField bounds="[676,1760][902,1838]" index="32">Photos</TextField>
      <Button description="Post Photos" bounds="[902,1736][1027,1861]" index="33" />
      <TextField bounds="[770,1890][902,1957]" index="34">Gif</TextField>
      <Button description="Post Gif" bounds="[902,1861][1027,1986]" index="35" />
      <TextField bounds="[735,2039][902,2106]" index="36">Post</TextField>
    </div>
    <Button description="New post" long-clickable="true" bounds="[891,2001][1038,2148]" index="37" />
  </div>

  <div bounds="[0,2190][1080,2337]" index="38">
    <div description="Home. New items" bounds="[0,2190][216,2337]" index="39" />
    <Button description="Search and Explore" bounds="[216,2190][432,2337]" index="40" />
    <Button description="Communities" bounds="[432,2190][648,2337]" index="41" />
    <Button description="Notifications" bounds="[648,2190][864,2337]" index="42" />
    <Button description="Messages" bounds="[864,2190][1080,2337]" index="43" />
  </div>

</div>

</screen>
Goal: On Zoom, edit my scheduled meeting 'Weekly group meeting', turn 'Enable waiting room' on.
Correct Action: {{"action_type": "click", "index": 37}} or {{"action_type": "click", "index": 36}}
"""

SCENARIO_SHOT_ACTION_EXAMPLE = """
Scenario Example: Open Snapchat spotlight page and like the first video.
This walkthrough demonstrates an entire task from start to finish. Use it as inspiration and then carefully plan what to do on the current screen.

Step 1:
<screen>
UI element 0: {"index": 0, "bounds": "[99,159][1023,430]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 1: {"index": 1, "text": "Wed, Nov 12", "content_description": "Wed, Nov 12", "bounds": "[99,227][1023,289]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 2: {"index": 2, "content_description": "Home", "bounds": "[0,63][1080,2337]", "is_enabled": "True"}
UI element 3: {"index": 3, "text": "Phone", "content_description": "Phone", "bounds": "[76,1873][249,2068]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 4: {"index": 4, "text": "Messages", "content_description": "Messages", "bounds": "[328,1873][501,2068]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 5: {"index": 5, "text": "Chrome", "content_description": "Chrome", "bounds": "[580,1873][753,2068]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 6: {"index": 6, "text": "Settings", "content_description": "Settings", "bounds": "[832,1873][1004,2068]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 7: {"index": 7, "content_description": "Search", "bounds": "[75,2125][1004,2290]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 8: {"index": 8, "content_description": "Google app", "bounds": "[86,2144][212,2270]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 9: {"index": 9, "content_description": "Voice search", "bounds": "[741,2125][867,2290]", "is_clickable": "True", "is_enabled": "True"}
UI element 10: {"index": 10, "content_description": "Google Lens", "bounds": "[867,2125][993,2290]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
</screen>
Action: {{"action_type": "openapp"}}
Description: Open Snapchat app.

Step 2:
<screen>
UI element 0: {"index": 0, "bounds": "[961,94][1045,178]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 1: {"index": 1, "bounds": "[962,210][1046,294]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 2: {"index": 2, "bounds": "[962,325][1046,409]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 3: {"index": 3, "bounds": "[962,440][1046,524]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 4: {"index": 4, "bounds": "[961,555][1045,639]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 5: {"index": 5, "bounds": "[962,683][1046,767]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 6: {"index": 6, "content_description": "Memories", "bounds": "[0,1773][105,1917]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 7: {"index": 7, "content_description": "Camera Capture", "bounds": "[393,1684][687,1978]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 8: {"index": 8, "bounds": "[0,2090][1080,2274]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 9: {"index": 9, "content_description": "Map", "bounds": "[0,2132][241,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 10: {"index": 10, "content_description": "Map", "bounds": "[100,2134][184,2218]", "is_enabled": "True"}
UI element 11: {"index": 11, "text": "Map", "bounds": "[110,2218][174,2261]", "is_enabled": "True"}
UI element 12: {"index": 12, "content_description": "Chat", "bounds": "[241,2132][440,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 13: {"index": 13, "content_description": "Chat", "bounds": "[299,2134][383,2218]", "is_enabled": "True"}
UI element 14: {"index": 14, "text": "Chat", "bounds": "[307,2218][375,2261]", "is_enabled": "True"}
UI element 15: {"index": 15, "content_description": "Camera", "bounds": "[440,2132][639,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 16: {"index": 16, "content_description": "Explore", "bounds": "[456,2132][624,2220]", "is_focusable": "True", "is_enabled": "True"}
UI element 17: {"index": 17, "text": "Explore", "bounds": "[484,2218][595,2261]", "is_enabled": "True"}
UI element 18: {"index": 18, "content_description": "Stories", "bounds": "[639,2132][838,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 19: {"index": 19, "content_description": "Stories", "bounds": "[697,2134][781,2218]", "is_enabled": "True"}
UI element 20: {"index": 20, "text": "Stories", "bounds": "[690,2218][788,2261]", "is_enabled": "True"}
UI element 21: {"index": 21, "content_description": "Spotlight", "bounds": "[838,2132][1079,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 22: {"index": 22, "content_description": "Spotlight", "bounds": "[896,2134][980,2218]", "is_enabled": "True"}
UI element 23: {"index": 23, "text": "Spotlight", "bounds": "[872,2218][1003,2261]", "is_enabled": "True"}
UI element 24: {"index": 24, "bounds": "[0,63][139,205]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 25: {"index": 25, "content_description": "Search", "bounds": "[152,79][257,184]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 26: {"index": 26, "bounds": "[823,79][928,184]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 27: {"index": 27, "content_description": "Add Friends", "bounds": "[825,92][909,171]", "is_enabled": "True"}

</screen>
Action: {{"action_type": "click", "index": 21}} or {{"action_type": "click", "index": 22}} or {{"action_type": "click", "index": 23}}
Desc

Step 3:
<screen>
UI element 0: {"index": 0, "text": "4.6M", "bounds": "[21,1810][933,1866]", "is_enabled": "True"}
UI element 1: {"index": 1, "bounds": "[21,1877][87,1943]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 2: {"index": 2, "text": "nevaaadaa", "bounds": "[108,1878][417,1942]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 3: {"index": 3, "bounds": "[21,1964][314,2069]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 4: {"index": 4, "text": "Remixes", "bounds": "[126,1972][264,2018]", "is_enabled": "True"}
UI element 5: {"index": 5, "text": "Tap to view", "bounds": "[126,2018][293,2062]", "is_enabled": "True"}
UI element 6: {"index": 6, "bounds": "[938,1291][1069,1450]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 7: {"index": 7, "bounds": "[938,1450][1069,1609]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 8: {"index": 8, "bounds": "[938,1609][1069,1768]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 9: {"index": 9, "text": "8.1K", "bounds": "[938,1714][1069,1768]", "is_enabled": "True"}
UI element 10: {"index": 10, "bounds": "[938,1768][1069,1927]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 11: {"index": 11, "text": "24K", "bounds": "[938,1873][1069,1927]", "is_enabled": "True"}
UI element 12: {"index": 12, "bounds": "[951,1964][1056,2069]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 13: {"index": 13, "bounds": "[0,2090][1080,2274]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 14: {"index": 14, "content_description": "Map", "bounds": "[0,2132][241,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 15: {"index": 15, "content_description": "Map", "bounds": "[100,2134][184,2218]", "is_enabled": "True"}
UI element 16: {"index": 16, "text": "Map", "bounds": "[110,2218][174,2261]", "is_enabled": "True"}
UI element 17: {"index": 17, "content_description": "Chat", "bounds": "[241,2132][440,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 18: {"index": 18, "content_description": "Chat", "bounds": "[299,2134][383,2218]", "is_enabled": "True"}
UI element 19: {"index": 19, "text": "Chat", "bounds": "[307,2218][375,2261]", "is_enabled": "True"}
UI element 20: {"index": 20, "content_description": "Camera", "bounds": "[440,2132][639,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 21: {"index": 21, "content_description": "Camera", "bounds": "[498,2134][582,2218]", "is_enabled": "True"}
UI element 22: {"index": 22, "text": "Camera", "bounds": "[483,2218][596,2261]", "is_enabled": "True"}
UI element 23: {"index": 23, "content_description": "Stories", "bounds": "[639,2132][838,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 24: {"index": 24, "content_description": "Stories", "bounds": "[697,2134][781,2218]", "is_enabled": "True"}
UI element 25: {"index": 25, "text": "Stories", "bounds": "[690,2218][788,2261]", "is_enabled": "True"}
UI element 26: {"index": 26, "content_description": "Spotlight", "bounds": "[838,2132][1079,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 27: {"index": 27, "content_description": "Spotlight", "bounds": "[896,2134][980,2218]", "is_enabled": "True"}
UI element 28: {"index": 28, "text": "Spotlight", "bounds": "[872,2218][1003,2261]", "is_enabled": "True"}
UI element 29: {"index": 29, "bounds": "[0,63][139,205]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 30: {"index": 30, "content_description": "Search", "bounds": "[152,79][257,184]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 31: {"index": 31, "text": "Spotlight", "bounds": "[428,63][651,205]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}

</screen>
Action: {{"action_type": "click", "index": 7}}

Step 4:
<screen>
UI element 0: {"index": 0, "text": "4.6M", "bounds": "[21,1810][933,1866]", "is_enabled": "True"}
UI element 1: {"index": 1, "bounds": "[21,1877][87,1943]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 2: {"index": 2, "text": "nevaaadaa", "bounds": "[108,1878][417,1942]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 3: {"index": 3, "bounds": "[21,1964][314,2069]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 4: {"index": 4, "text": "Remixes", "bounds": "[126,1972][264,2018]", "is_enabled": "True"}
UI element 5: {"index": 5, "text": "Tap to view", "bounds": "[126,2018][293,2062]", "is_enabled": "True"}
UI element 6: {"index": 6, "bounds": "[938,1291][1069,1450]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 7: {"index": 7, "bounds": "[938,1450][1069,1609]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 8: {"index": 8, "bounds": "[938,1609][1069,1768]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 9: {"index": 9, "text": "8.1K", "bounds": "[938,1714][1069,1768]", "is_enabled": "True"}
UI element 10: {"index": 10, "bounds": "[938,1768][1069,1927]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 11: {"index": 11, "text": "24K", "bounds": "[938,1873][1069,1927]", "is_enabled": "True"}
UI element 12: {"index": 12, "bounds": "[951,1964][1056,2069]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 13: {"index": 13, "bounds": "[0,2090][1080,2274]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 14: {"index": 14, "content_description": "Map", "bounds": "[0,2132][241,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 15: {"index": 15, "content_description": "Map", "bounds": "[100,2134][184,2218]", "is_enabled": "True"}
UI element 16: {"index": 16, "text": "Map", "bounds": "[110,2218][174,2261]", "is_enabled": "True"}
UI element 17: {"index": 17, "content_description": "Chat", "bounds": "[241,2132][440,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 18: {"index": 18, "content_description": "Chat", "bounds": "[299,2134][383,2218]", "is_enabled": "True"}
UI element 19: {"index": 19, "text": "Chat", "bounds": "[307,2218][375,2261]", "is_enabled": "True"}
UI element 20: {"index": 20, "content_description": "Camera", "bounds": "[440,2132][639,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 21: {"index": 21, "content_description": "Camera", "bounds": "[498,2134][582,2218]", "is_enabled": "True"}
UI element 22: {"index": 22, "text": "Camera", "bounds": "[483,2218][596,2261]", "is_enabled": "True"}
UI element 23: {"index": 23, "content_description": "Stories", "bounds": "[639,2132][838,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 24: {"index": 24, "content_description": "Stories", "bounds": "[697,2134][781,2218]", "is_enabled": "True"}
UI element 25: {"index": 25, "text": "Stories", "bounds": "[690,2218][788,2261]", "is_enabled": "True"}
UI element 26: {"index": 26, "content_description": "Spotlight", "bounds": "[838,2132][1079,2263]", "is_clickable": "True", "is_long_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 27: {"index": 27, "content_description": "Spotlight", "bounds": "[896,2134][980,2218]", "is_enabled": "True"}
UI element 28: {"index": 28, "text": "Spotlight", "bounds": "[872,2218][1003,2261]", "is_enabled": "True"}
UI element 29: {"index": 29, "bounds": "[0,63][139,205]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 30: {"index": 30, "content_description": "Search", "bounds": "[152,79][257,184]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}
UI element 31: {"index": 31, "text": "Spotlight", "bounds": "[428,63][651,205]", "is_clickable": "True", "is_focusable": "True", "is_enabled": "True"}

</screen>
Action: {{"action_type": "finish"}}
"""


POST_SUMMARIZATION_PROMPT_TEMPLATE = (
        '{prefix}'
        + '\nThe (overall) user goal/request is:{goal}\n'
          'Now I want you to summerize the latest step based on the action you'
          ' picked and descriptions of the screen before and after the action.\n'
          'Here is the UI representation (description) of the screen before the action:'
          '\n{before_elements}\n'
          'On this screen, you have performed the following action: \n{action}\n'
          'Based on the reason: \n{reason}\n'
          'After the action, the screen is now:\n{after_elements}\n'
          '\nBy comparing the descriptions for the two screenshots and the action'
          ' performed, give a brief summary of this step.'
          ' This summary will be added to action history and used in future action'
          ' selection, so try to include essential information you think that will'
          ' be most useful for future action selection like'
          ' what you intended to do, why, if it worked as expected, if not'
          ' what might be the reason (be critical, the action/reason might not be'
          ' correct), what should/should not be done next and so on. Some more'
          ' rules/tips you should follow:\n'
          '- Keep it short and in one line.\n'
          "- Some actions (like `answer`, `wait`) don't involve screen change,"
          ' you can just assume they work as expected.\n'
          '- Given this summary will be added into action history, it can be used as'
          ' memory to include information that needs to be remembered.\n\n'
          'Summary of this step: '
)

PRE_SUMMARIZATION_PROMPT_TEMPLATE = (
    '{prefix}'
    + '\nThe (overall) user goal/request is:{goal}\n'
    + 'Now I want you to summerize the latest step based on the action you'
    ' picked and the description of the screen before the action.\n'
    'Here is the HTML representation (description) of the screen before the action:'
    '\n{before_elements}\n'
    'On this screen, you have performed the following action: \n{action}\n'
    'Based on the reason: \n{reason}\n'
    + '\nBased on the screen description, the action performed, and the reason,'
    ' give a brief summary of this step.'
    ' This summary will be added to action history and used in future action'
    ' selection, so try to include essential information you think that will'
    ' be most useful for future action selection like'
    ' what you intended to do, why you chose this action, and what you expect to happen as a result. Some more' # 'if it worked as expected' 부분을 'what you expect to happen'으로 변경
    ' rules/tips you should follow:\n'
    '- Keep it short and in one line.\n'
    '- Given this summary will be added into action history, it can be used as'
    ' memory to include information that needs to be remembered.\n\n'
    'Summary of this step: '
)

POST_SUMMARIZATION_PROMPT_TEMPLATE_MM_CLICK = (
        PROMPT_PREFIX_SUMMARIZE
        + '\nThe (overall) user goal/request is:{goal}\n\n'
          'Now I want you to summerize the latest step based on the action you'
          ' pick with the reason and descriptions for the before and after (the'
          ' action) screenshots.\n\n'
          'Here is the UI representation (description) of the screen before the action (related with first image):'
          '\n{before_elements}\n\n'

          'On this screen you chose the following action(For the click action, the interaction is indicated by the RED cross in the first screen image.):\n{action}\n\n'

          'additionally, give you an index of the XML tags that contain the click coordinates for that action within the bound.(from the previous screen) The later the index mentioned, the closer it is to the last child node.(The closer it is to the last child node, the more it will be displayed at the top.) Use this as a guide to determine what UI you are interacting with (if not present, the tag was not extracted in the XML, so you\'ll have to judge by looking at the image):\n{related_xml_tags}\n\n'

          'Here is the UI representation (description) of the screen after the action (related with second image):'
          '\n{after_elements}\n\n'

          'By comparing the descriptions for the two screenshots and the action'
          ' performed, give a brief summary of this step.'
          ' This summary will be added to action history and used in future action'
          ' selection, so try to include essential information you think that will'
          ' be most useful for future action selection like'
          ' what you intended to do, why, if it worked as expected, if not'
          ' what might be the reason (be critical, the action/reason might not be'
          ' correct), what should/should not be done next and so on. Some more'
          ' rules/tips you should follow:\n'
          '- Keep it short and in one line.\n'
          '- Given this summary will be added into action history, it can be used as'
          ' memory to include information that needs to be remembered.\n\n'
          'Summary of this step: '
)

PRE_SUMMARIZATION_PROMPT_TEMPLATE_MM_CLICK = (
    PROMPT_PREFIX_SUMMARIZE
    + '\nThe (overall) user goal/request is:{goal}\n\n'
    # 'and after' 부분을 삭제
    + 'Now I want you to summerize the latest step based on the action you'
    ' pick with the reason and the description for the before (the'
    ' action) screenshot.\n\n'
    'Here is the UI representation (description) of the screen before the action (related with the image):'
    '\n{before_elements}\n\n'

    'On this screen you chose the following action(For the click action, the interaction is indicated by the RED cross in the image.):\n{action}\n\n'

    'additionally, give you an index of the XML tags that contain the click coordinates for that action within the bound.(from the previous screen) The later the index mentioned, the closer it is to the last child node.(The closer it is to the last child node, the more it will be displayed at the top.) Use this as a guide to determine what UI you are interacting with (if not present, the tag was not extracted in the XML, so you\'ll have to judge by looking at the image):\n{related_xml_tags}\n\n'

    + 'By comparing the description for the screenshot and the action'
    ' performed, give a brief summary of this step.'
    ' This summary will be added to action history and used in future action'
    ' selection, so try to include essential information you think that will'
    ' be most useful for future action selection like'
    ' what you intended to do, why you chose this action, and what you expect to happen as a result. Some more' # 'if it worked as expected' 부분을 'what you expect to happen'으로 변경
    ' rules/tips you should follow:\n'
    '- Keep it short and in one line.\n'
    '- Given this summary will be added into action history, it can be used as'
    ' memory to include information that needs to be remembered.\n\n'
    'Summary of this step: '
)

POST_SUMMARIZATION_PROMPT_TEMPLATE_MM = (
        PROMPT_PREFIX_SUMMARIZE
        + '\nThe (overall) user goal/request is:{goal}\n\n'
          'Now I want you to summerize the latest step based on the action you'
          ' pick with the reason and descriptions for the before and after (the'
          ' action) screenshots.\n\n'
          'Here is the UI representation (description) of the screen before the action (related with first image):'
          '\n{before_elements}\n\n'

          'On this screen you chose the following action:\n {action}\n\n'

          'Here is the UI representation (description) of the screen after the action (related with second image):'
          '\n{after_elements}\n\n'

          'By comparing the descriptions for the two screenshots and the action'
          ' performed, give a brief summary of this step.'
          ' This summary will be added to action history and used in future action'
          ' selection, so try to include essential information you think that will'
          ' be most useful for future action selection like'
          ' what you intended to do, why, if it worked as expected, if not'
          ' what might be the reason (be critical, the action/reason might not be'
          ' correct), what should/should not be done next and so on. Some more'
          ' rules/tips you should follow:\n'
          '- Keep it short and in one line.\n'
          "- Some actions (like answer, wait) don't involve screen change,"
          ' you can just assume they work as expected.\n'
          '- Given this summary will be added into action history, it can be used as'
          ' memory to include information that needs to be remembered.\n\n'
          'Summary of this step: '
)

PRE_SUMMARIZATION_PROMPT_TEMPLATE_MM = (
    PROMPT_PREFIX_SUMMARIZE
    + '\nThe (overall) user goal/request is:{goal}\n\n'
    # 'and after' 부분을 삭제
    + 'Now I want you to summerize the latest step based on the action you'
    ' pick with the reason and the description for the before (the'
    ' action) screenshot.\n\n'
    # 'first image'라는 표현을 단순히 'the image'로 변경해도 좋습니다.
    'Here is the UI representation (description) of the screen before the action (related with the image):'
    '\n{before_elements}\n\n'

    'On this screen you chose the following action:\n {action}\n\n'

    # 'after' 화면에 대한 블록 전체를 삭제
    
    # 'two screenshots'를 'the screenshot'으로 변경하고, 지시사항을 '의도'와 '예상'에 집중하도록 수정
    + '\nBased on the screen description, the action performed, and the reason,'
    ' give a brief summary of this step.'
    ' This summary will be added to action history and used in future action'
    ' selection, so try to include essential information you think that will'
    ' be most useful for future action selection like'
    ' what you intended to do, why you chose this action, and what you expect to happen as a result. Some more' # 'if it worked as expected' 부분을 'what you expect to happen'으로 변경
    ' rules/tips you should follow:\n'
    '- Keep it short and in one line.\n'
    "- Some actions (like answer, wait) don't involve screen change,"
    ' you can just assume they work as expected.\n'
    '- Given this summary will be added into action history, it can be used as'
    ' memory to include information that needs to be remembered.  \n\n'
    'Summary of this step: '
)

VERIFICATION_ACTION_PROMPT_TEMPLATE_MM_SINGLE_SCREEN = (
        PROMPT_PREFIX_VERIFICATION
        + '\nThe (overall) user goal/request is: {goal}\n'
          'Here is a history of what you have done so far:\n{history}\n'
          'Now I want you to verify whether the next chosen action is correct.\n'
          'Here is the description of the screen before the action:'
          '\n{before_elements}\n'
          'On this screen you chose the following action: {action}\n\n'
          'Your task is to determine if the action is correct given the'
          ' screen before the action. The action is correct if it brings the user one step closer to the goal. It does not have to be the best option.\n'
          'Respond with the result in JSON format.\n'
          '- Include "correct" (boolean) indicating if the action is correct.\n'
          '- Include "explanation" (string) explaining the reasoning.\n'
          '- If the action is incorrect, include "feedback" (string) providing feedback on what went wrong and how to fix it if applicable, or "none" if no fixes are needed.\n\n'
          'Response format:\n'
          '{{\n'
          '  "correct": true/false,\n'
          '  "explanation": "Your explanation here.",\n'
          '  "feedback": "Explanation of how to fix the issue or none if no fixes are needed."\n'
          '}}\n\n'
          'Verification result: '
)

VERIFICATION_ACTION_PROMPT_TEMPLATE_MM_MULTI_SCREEN_CLICK = (
        PROMPT_PREFIX_VERIFICATION
        + '\nThe (overall) user goal/request is: {goal}\n\n'
          'Here is a history of what you have done so far:\n{history}\n\n'
          '***Now I want you to verify whether the chosen action is correct based'
          ' on the screen before and after the action.***\n\n'
          'Here is the UI representation (description) of the screen before the action (related with first image):'
          '\n{before_elements}\n\n'

          'On this screen you chose the following action(For the click action, the interaction is indicated by the RED cross in the first screen image.):\n{action}\n\n'

          'additionally, give you an index of the XML tags that contain the click coordinates for that action within the bound.(from the previous screen) The later the index mentioned, the closer it is to the last child node.(The closer it is to the last child node, the more it will be displayed at the top.) Use this as a guide to determine what UI you are interacting with (if not present, the tag was not extracted in the XML, so you\'ll have to judge by looking at the image):\n{related_xml_tags}\n\n'

          'Here is the UI representation (description) of the screen after the action (related with second image):'
          '\n{after_elements}\n\n'

          'To achieve a user\'s goal, you may need to go through multiple actions. You need to understand the history of previous actions and the current action. If the action is a reasonable path to achieving the user\'s goal, it is the correct action. It does not have to be the best option.\n\n'
          'Respond with the result in JSON format.\n'
          '- Include "correct" (boolean) indicating if the action is correct.\n'
          '- Include "explanation" (string) explaining the reasoning.\n'
          '- If the action is incorrect, include "feedback" (string) providing feedback on what went wrong and how to fix it if applicable, or "none" if no fixes are needed.\n\n'
          'Response format:\n'
          '{{\n'
          '  "correct": true/false,\n'
          '  "explanation": "Your explanation here. why you think the action is correct or incorrect.",\n'
          '  "feedback": "Explanation of how to fix the issue or none if no fixes are needed."\n'
          '}}\n\n'
          'Verification result: '
)

VERIFICATION_ACTION_PROMPT_TEMPLATE_MM_MULTI_SCREEN = (
        PROMPT_PREFIX_VERIFICATION
        + '\nThe (overall) user goal/request is: {goal}\n\n'
          'Here is a history of what you have done so far:\n{history}\n\n'
          '***Now I want you to verify whether the chosen action is correct based'
          ' on the screen before and after the action.***\n\n'
          'Here is the UI representation (description) of the screen before the action (related with first image):'
          '\n{before_elements}\n\n'

          'On this screen you chose the following action:\n {action}\n\n'

          'Here is the UI representation (description) of the screen after the action (related with second image):'
          '\n{after_elements}\n\n'

          'To achieve a user\'s goal, you may need to go through multiple actions. You need to understand the history of previous actions and the current action. If the action is a reasonable path to achieving the user\'s goal, it is the correct action. It does not have to be the best option.\n\n'
          'Respond with the result in JSON format.\n'
          '- Include "correct" (boolean) indicating if the action is correct.\n'
          '- Include "explanation" (string) explaining the reasoning.\n'
          '- If the action is incorrect, include "feedback" (string) providing feedback on what went wrong and how to fix it if applicable, or "none" if no fixes are needed.\n\n'
          'Response format:\n'
          '{{\n'
          '  "correct": true/false,\n'
          '  "explanation": "Your explanation here. why you think the action is correct or incorrect.",\n'
          '  "feedback": "Explanation of how to fix the issue or none if no fixes are needed."\n'
          '}}\n\n'
          'Verification result: '
)

VERIFICATION_TASK_PROMPT_TEMPLATE_MM = (
        PROMPT_PREFIX_VERIFICATION_HISTORY
        + '\nThe (overall) user goal/request is: {goal}\n'
          'You will be provided with a list of action summaries that represent the'
          ' steps taken so far toward completing the task.\n\n'
          'Here is the list of action summaries (in chronological order):\n'
          '{action_history}\n\n'
          'Your task is to verify whether the current path is correct and aligned with achieving the goal.\n'
          'If the path is incorrect, provide feedback on what went wrong and how to correct it.\n\n'
          'Respond in JSON format with the following fields:\n'
          '- "correct" (boolean) indicating if the sequence of actions taken so far is correct.\n'
          '- "explanation" (string) summarizing why the path is or is not correct.\n'
          '- "feedback" (string) providing feedback on what went wrong and how to fix it if applicable, or "none" if no fixes are needed.\n\n'
          'Response format:\n'
          '{{\n'
          '  "correct": true/false,\n'
          '  "explanation": "Your explanation here.",\n'
          '  "feedback": "Explanation of how to fix the issue or none if no fixes are needed."\n'
          '}}\n\n'
          'Verification result: '
)


def _action_selection_prompt(
        goal: str,
        history: list[str],
        ui_elements_description: str,
        additional_guidelines: list[str] | None = None,
        mm: bool = False,
        isxml: bool = True,
        prompt_type: str = 'react',
        image_only: bool = False
) -> str:
    """Generate the prompt for the action selection.

    Args:
      goal: The current task goal.
      history: Summaries for previous steps.
      ui_elements_description: A list of descriptions for the UI elements.
      additional_guidelines: Task specific guidelines.
      image_only: Flag to use the image-only prompt variation.

    Returns:
      The text prompt for action selection that will be sent to gpt4v.
    """
    # Build history text without any default starter line
    hist_text = ''
    for i, action_text in enumerate(history):
        hist_text += f"{action_text}\n"

    extra_guidelines = ''
    if additional_guidelines:
        extra_guidelines = 'For The Current Task:\n'
        for guideline in additional_guidelines:
            extra_guidelines += f'- {guideline}\n'

    if image_only:
      if prompt_type in ('pure_action', 'few_shot', 'scenario_shot'):
        template = IMAGE_ONLY_PURE_ACTION_SELECTION_PROMPT_TEMPLATE
      else:
        template = IMAGE_ONLY_ACTION_SELECTION_PROMPT_TEMPLATE

      few_shot_example = ''
      if prompt_type == 'few_shot':
        few_shot_example = FEW_SHOT_ACTION_EXAMPLE
      elif prompt_type == 'scenario_shot':
        few_shot_example = SCENARIO_SHOT_ACTION_EXAMPLE

      return template.format(
        prefix=IMAGE_ONLY_PROMPT_PREFIX,
        history=hist_text,
        goal=goal,
        additional_guidelines=extra_guidelines,
        few_shot_example=few_shot_example,
      )

    if isxml:
        prefix = PROMPT_PREFIX_WITH_XML
    else:
        prefix = PROMPT_PREFIX_WITHOUT_XML

    if prompt_type == 'react':
        return REACT_ACTION_SELECTION_PROMPT_TEMPLATE.format(
            prefix=prefix,
            history=hist_text,
            goal=goal,
            ui_elements_description=ui_elements_description
            if ui_elements_description
            else 'Not available',
            additional_guidelines=extra_guidelines,
        )
    elif prompt_type == 'pure_action':
        # Ensure history is a newline-joined string, not a Python list repr
        return PURE_ACTION_SELECTION_PROMPT_TEMPLATE.format(
            prefix=prefix,
            few_shot_example='',
            history=hist_text,
            goal=goal,
            ui_elements_description=ui_elements_description
            if ui_elements_description
            else 'Not available',
            additional_guidelines=extra_guidelines,
        )
    elif prompt_type == 'few_shot':
        return PURE_ACTION_SELECTION_PROMPT_TEMPLATE.format(
            prefix=prefix,
            few_shot_example=FEW_SHOT_ACTION_EXAMPLE,
            history=hist_text,
            goal=goal,
            ui_elements_description=ui_elements_description
            if ui_elements_description
            else 'Not available',
            additional_guidelines=extra_guidelines,
        )
    elif prompt_type == 'scenario_shot':
        return PURE_ACTION_SELECTION_PROMPT_TEMPLATE.format(
            prefix=prefix,
            few_shot_example=SCENARIO_SHOT_ACTION_EXAMPLE,
            history=hist_text,
            goal=goal,
            ui_elements_description=ui_elements_description
            if ui_elements_description
            else 'Not available',
            additional_guidelines=extra_guidelines,
        )
    elif prompt_type == 'f-react':
        return REACT_ACTION_SELECTION_PROMPT_TEMPLATE.format(
            prefix=prefix + '\n' + FEW_SHOT_ACTION_EXAMPLE,
            history=hist_text,
            goal=goal,
            ui_elements_description=ui_elements_description
            if ui_elements_description
            else 'Not available',
            additional_guidelines=extra_guidelines,
        )


def _verify_action_prompt(goal: str, action: str, history: list, before_elements: str, mm: bool = True) -> str:
    if history:
        history = '\n'.join(history)
    else:
        history = ''

    if mm:
        return VERIFICATION_ACTION_PROMPT_TEMPLATE_MM_SINGLE_SCREEN.format(
            goal=goal,
            action=action,
            history=history,
            before_elements=before_elements,
        )
    else:
        return None

def _summarize_prompt(
        goal: str,
        action: str,
        reason: str,
        before_elements: str,
        after_elements: str,
        mm: bool = False,
        isxml: bool = True,
        summary_type: str = 'post'
) -> str:
    """Generate the prompt for the summarization step.

    Args:
      goal: The overall goal.
      action: The action picked for the step.
      reason: The reason why pick the action.
      before_elements: Information for UI elements on the before screenshot.
      after_elements: Information for UI elements on the after screenshot.

    Returns:
      The text prompt for summarization that will be sent to gpt4v.
    """

    action = json.loads(action)

    if summary_type == 'post':
        return POST_SUMMARIZATION_PROMPT_TEMPLATE_MM.format(
            prefix=PROMPT_PREFIX_SUMMARIZE,
            goal=goal,
            action=action,
            before_elements=before_elements if before_elements else 'Not available',
            after_elements=after_elements if after_elements else 'Not available'
        )
    elif summary_type == 'pre':
        return PRE_SUMMARIZATION_PROMPT_TEMPLATE_MM.format(
            prefix=PROMPT_PREFIX_SUMMARIZE,
            goal=goal,
            action=action,
            before_elements=before_elements if before_elements else 'Not available',
        )
    else:
        return PRE_SUMMARIZATION_PROMPT_TEMPLATE.format(
            prefix=PROMPT_PREFIX_SUMMARIZE,
            goal=goal,
            action=action,
            reason=reason,
            before_elements=before_elements if before_elements else 'Not available',
            after_elements=after_elements if after_elements else 'Not available',
        )

def _verify_action_prompt_after(goal: str, action: str, history: list, before_elements: str, after_elements: str, mm: bool = True) -> str:
    related_xml_tags = ''

    if history:
        history = '\n'.join(history)
    else:
        history = ''

    action = json.loads(action)

    if mm:
        if action["action_type"] == "click":
            return VERIFICATION_ACTION_PROMPT_TEMPLATE_MM_MULTI_SCREEN_CLICK.format(
                goal=goal,
                action={"action_type": "click", "clicked_coordinates": action["clicked_coordinates"]},
                history=history,
                before_elements=before_elements,
                after_elements=after_elements,
                related_xml_tags=action["clicked_index"],
            )
        else:
            return VERIFICATION_ACTION_PROMPT_TEMPLATE_MM_MULTI_SCREEN.format(
                goal=goal,
                action=action,
                history=history,
                before_elements=before_elements,
                after_elements=after_elements,
            )
    else:
        return None

def _verify_history_prompt(goal: str, history: list, mm: bool = True) -> str:
    if history:
        history = '\n'.join(history)
    else:
        history = ''

    if mm:
        return VERIFICATION_TASK_PROMPT_TEMPLATE_MM.format(
            goal=goal,
            action_history=history,
        )
    else:
        return None



