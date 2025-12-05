import re
import os
from collections import Counter

def find_and_count_errors_with_index(file_path):
    """
    1. 첫 번째 'openapp' 단계는 실패하고 모든 후속 단계는 성공한 작업을 찾습니다.
    2. 실패한 첫 단계의 예측값(Action Type + Index)을 추출하여 카운트합니다.
    """
    if not os.path.exists(file_path):
        print(f"오류: 파일 경로를 찾을 수 없습니다. '{file_path}'")
        return [], Counter()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"오류: 파일을 읽는 중 문제가 발생했습니다. {e}")
        return [], Counter()

    matched_tasks = []
    error_stats = Counter()

    task_split_pattern = r"(--- Task Timing ---[\s\S]*?Task:.*?\n)"
    chunks = re.split(task_split_pattern, content)

    if not chunks:
        print("로그에서 작업 내용을 찾을 수 없습니다.")
        return [], Counter()

    for i in range(0, len(chunks) - 1, 2):
        steps_block = chunks[i]
        timing_block = chunks[i+1]

        if not steps_block.strip():
            continue

        steps = re.split(r'--- Default Action Determined ---', steps_block)
        valid_steps = [s for s in steps if s.strip()]

        if not valid_steps:
            continue

        # --- 조건 1 확인 ---
        first_step_content = valid_steps[0]
        is_first_step_openapp = "'action_type': 'openapp'" in first_step_content
        is_first_step_failed = "Final Matching Result: False" in first_step_content

        if not (is_first_step_openapp and is_first_step_failed):
            continue

        # --- 조건 2 확인 ---
        all_subsequent_steps_true = True
        subsequent_steps = valid_steps[1:]
        if subsequent_steps:
            for step_content in subsequent_steps:
                if "Final Matching Result: True" not in step_content:
                    all_subsequent_steps_true = False
                    break

        if all_subsequent_steps_true:
            # --- 정보 추출 로직 개선 (Index 포함) ---
            # 1. Predicted Action 라인 찾기
            pred_line_match = re.search(r"Predicted Action: (\{.*?\})", first_step_content)
            
            final_action_str = "Unknown"
            
            if pred_line_match:
                pred_dict_str = pred_line_match.group(1)
                
                # action_type 추출
                type_match = re.search(r"'action_type':\s*'(?P<type>[^']+)'", pred_dict_str)
                action_type = type_match.group("type") if type_match else "Unknown"
                
                # index 추출 (숫자 또는 None)
                index_match = re.search(r"'index':\s*(?P<idx>[0-9]+|None)", pred_dict_str)
                action_index = index_match.group("idx") if index_match else "None"

                # 출력 문자열 조합
                if action_index != "None":
                    final_action_str = f"{action_type} (idx: {action_index})"
                else:
                    final_action_str = action_type

            # 통계 업데이트
            error_stats[final_action_str] += 1

            # Task 정보 저장
            task_info = re.search(
                r"Task: (?P<id>.*?),\s*Instruction: (?P<inst>.*?),\s*Success: (?P<succ>.*?),",
                timing_block,
                re.DOTALL
            )
            
            if task_info:
                matched_tasks.append({
                    "Task ID": task_info.group("id").strip(),
                    "Instruction": task_info.group("inst").strip(),
                    "Wrong Prediction": final_action_str
                })

    return matched_tasks, error_stats

# --- 실행부 ---
if __name__ == "__main__":
    log_file_path = input("분석할 로그 파일의 전체 경로를 입력하세요: ")

    tasks, stats = find_and_count_errors_with_index(log_file_path)

    if not tasks:
        print("\n조건을 만족하는 작업을 찾지 못했습니다.")
    else:
        print(f"\n=== 분석 결과 (총 {len(tasks)}건 발견) ===")
        print("-" * 40)
        
        print("📊 [OpenApp 대신 선택된 행동 통계]")
        # 많이 나온 순서대로 출력
        for action, count in stats.most_common():
            print(f"  - {action}: {count}회")
        
        print("-" * 40)

        print("📝 [세부 작업 목록]")
        for i, task in enumerate(tasks, 1):
            print(f"#{i} [Task {task['Task ID']}] -> 오답: {task['Wrong Prediction']}")
            print(f"   Instruction: {task['Instruction']}")