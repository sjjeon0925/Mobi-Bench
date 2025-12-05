import re
import os

def find_special_failed_tasks(file_path):
    """
    로그 파일에서 첫 번째 'openapp' 단계는 실패하고
    모든 후속 단계는 성공한 작업을 찾습니다.
    """
    if not os.path.exists(file_path):
        print(f"오류: 파일 경로를 찾을 수 없습니다. '{file_path}'")
        return []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"오류: 파일을 읽는 중 문제가 발생했습니다. {e}")
        return []

    matched_tasks = []

    # '--- Task Timing ---' 블록을 기준으로 전체 로그를 개별 작업으로 분리합니다.
    # 정규식을 사용하여 Task Timing 블록 자체도 캡처합니다.
    task_split_pattern = r"(--- Task Timing ---[\s\S]*?Task:.*?\n)"
    
    # re.split은 구분자(timing_block)를 포함하여 리스트를 반환합니다.
    # [steps_task_1, timing_block_1, steps_task_2, timing_block_2, ...]
    chunks = re.split(task_split_pattern, content)

    if not chunks:
        print("로그에서 작업 내용을 찾을 수 없습니다.")
        return []

    # 짝수 인덱스(steps)와 홀수 인덱스(timing)를 묶어서 처리
    for i in range(0, len(chunks) - 1, 2):
        steps_block = chunks[i]
        timing_block = chunks[i+1]

        if not steps_block.strip():
            continue

        # 개별 작업의 단계를 '--- Default Action Determined ---' 기준으로 나눔
        steps = re.split(r'--- Default Action Determined ---', steps_block)
        
        # 첫 번째 빈 문자열 등을 제거하고 내용이 있는 단계만 필터링
        valid_steps = [s for s in steps if s.strip()]

        if not valid_steps:
            continue

        # --- 조건 1: 첫 번째 단계가 'openapp'이고 'False'인지 확인 ---
        first_step_content = valid_steps[0]
        
        # Default Action에 'openapp'이 있는지 확인
        is_first_step_openapp = "'action_type': 'openapp'" in first_step_content
        # 'Final Matching Result: False'인지 확인
        is_first_step_failed = "Final Matching Result: False" in first_step_content

        if not (is_first_step_openapp and is_first_step_failed):
            # 조건 1을 만족하지 않으면 다음 작업으로 넘어감
            continue

        # --- 조건 2: 나머지 모든 단계가 'True'인지 확인 ---
        all_subsequent_steps_true = True
        subsequent_steps = valid_steps[1:]

        if not subsequent_steps:
            # 후속 단계가 아예 없는 경우도 조건 2를 만족한 것으로 간주
            pass
        else:
            for step_content in subsequent_steps:
                if "Final Matching Result: True" not in step_content:
                    all_subsequent_steps_true = False
                    break # 하나라도 False이면 루프 중단

        # --- 최종 확인: 두 조건을 모두 만족하는지 ---
        if all_subsequent_steps_true:
            # Task Timing 블록에서 정보 추출
            task_info = re.search(
                r"Task: (?P<id>.*?),\s*Instruction: (?P<inst>.*?),\s*Success: (?P<succ>.*?),",
                timing_block,
                re.DOTALL
            )
            
            if task_info:
                matched_tasks.append({
                    "Task ID": task_info.group("id").strip(),
                    "Instruction": task_info.group("inst").strip(),
                    "Success": task_info.group("succ").strip(),
                    "Raw Timing Block": timing_block.strip()
                })

    return matched_tasks

# --- 스크립트 실행 ---
if __name__ == "__main__":
    # 여기에 실제 로그 파일 경로를 입력하세요.
    # 예: log_file_path = "C:/Users/YourUser/Desktop/my_log.txt"
    # 예: log_file_path = "/home/youruser/logs/my_log.txt"
    
    log_file_path = input("분석할 로그 파일의 전체 경로를 입력하세요: ")

    matching_tasks = find_special_failed_tasks(log_file_path)

    if not matching_tasks:
        print("\n조건을 만족하는 작업을 찾지 못했습니다.")
    else:
        print(f"\n총 {len(matching_tasks)}개의 조건 만족 작업을 찾았습니다:")
        print("=" * 30)
        for i, task in enumerate(matching_tasks, 1):
            print(f"--- 작업 #{i} ---")
            print(f"  Task ID: {task['Task ID']}")
            print(f"  Instruction: {task['Instruction']}")
            print(f"  Success: {task['Success']}")
            # print(f"  {task['Raw Timing Block']}") # 원본 타이밍 블록을 보려면 주석 해제
            print("-" * 30)