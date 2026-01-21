from agent.base_agent import Agent, AgentInteractionResult
from benchmark.base_benchmark import Benchmark
from environment.base_env import Env
import os
import json
import time
import gc
from datetime import datetime

from utils import log

target_tasks = [2]
PRINT_ON_FILE = False

def _numeric_sort_key(entry: str) -> tuple[int, object]:
    """Sort digits numerically but keep non-digits in lexicographic order."""
    return (0, int(entry)) if entry.isdigit() else (1, entry)

class BenchmarkAgentBench(Benchmark):
    def __init__(self, name: str, env: Env, agent: Agent):
        super().__init__(name, env, agent)
        # Override results_dir to match agent-centric folder naming with run tag
        agent_folder_map = {
            "image_with_explanation": "iwe",
            "xml_only": "xml_only",
            "image_only": "image_only",
            "divandconq": "divandconq",
            "divandconq_text": "divandconq_text",
        }
        folder = agent_folder_map.get(agent.name, agent.name)

        parser_name = getattr(self.env.parser, "name", "parser")
        som_mode = getattr(agent, "som_mode", "nosom")
        summary_type = getattr(agent, "summary_type", "none")
        prompt_type = getattr(agent, "prompt_type", getattr(agent, "name", "prompt"))
        reflection_type = getattr(agent, "reflection_type", "no_reflection")
        model_name = getattr(agent.model, "name", "model").replace("/", "-")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        run_tag = (
            f"{timestamp}_{parser_name}_{som_mode}"
            f"_summary_{summary_type}_model_{model_name}_prompt_{prompt_type}_reflect_{reflection_type}"
        )

        self.results_dir = os.path.join("./results", folder, run_tag)
        os.makedirs(self.results_dir, exist_ok=True)
        # Keep tasks under their own subfolders later when setting results_path
        self.base_task_dir = f"./dataset"
        self.total_action_len = 0
        self.total_success_len = 0
        self.success_instruction = 0
        self.total_instruction = 0
        self.action_attempts_with_retry = 0
        self.action_success_with_retry = 0
        self.action_attempts_without_retry = 0
        self.action_success_without_retry = 0
        self.task_attempts_with_retry = 0
        self.task_success_with_retry = 0
        self.task_attempts_without_retry = 0
        self.task_success_without_retry = 0

    def run(self):
        import sys
        self.env.load_env()
        benchmark_start_ts = time.perf_counter()
        benchmark_start_wall = time.strftime("%Y-%m-%d %H:%M:%S")

        def _format_rate(success: int, total: int) -> str:
            if total == 0:
                return f"{success}/{total} (N/A)"
            return f"{success}/{total} = {success / total:.2%}"

        for app_name in os.listdir(self.base_task_dir):
            if app_name in ['.DS_Store', 'results']:
                continue

            results = []
            self.results[app_name] = results
            cur_app_success_list = []
            app_dir = os.path.join(self.base_task_dir, app_name)
            self.env.app_dir = app_name

            if not os.path.isdir(app_dir):
                continue

            for task_name in sorted(os.listdir(app_dir), key=_numeric_sort_key):
                if task_name in ['.DS_Store', 'backup']:
                    continue

                # 폴더명이 숫자이고, target_tasks 리스트에 해당 숫자가 포함되어 있는지 확인
                if target_tasks and task_name.isdigit():
                    if int(task_name) not in target_tasks:
                        continue  # 리스트에 없는 번호는 건너뜀
                # if int(task_name) <= 0 or int(task_name) > 50:
                #     continue

                self.env.task_name = task_name
                task_dir = os.path.join(app_dir, task_name)
                original_stdout = sys.stdout 
                task_log_path = os.path.join(self.results_dir, f"{task_name}.txt")
                print("task dir", task_dir)
                if not os.path.isdir(task_dir):
                    continue 

                max_step = self.env.load_task(task_dir)
                self.env.results_path = self.results_dir
                os.makedirs(self.env.results_path, exist_ok=True)

                task_start_ts = time.perf_counter()
                task_start_wall = time.strftime("%Y-%m-%d %H:%M:%S")

                instruction_file = os.path.join(task_dir, "instruction.txt")
                if os.path.exists(instruction_file):
                    with open(instruction_file, 'r', encoding='utf-8') as file:
                        raw_instruction = file.read().strip()
                        if raw_instruction:
                            instruction = raw_instruction.replace('\r', ' ').replace('\n', ' ').strip()
                        else:
                            instruction = task_name.replace("_", " ")
                else:
                    instruction = task_name.replace("_", " ")

                step = 0
                self.env.instruction = instruction
                self.agent.reset(instruction)
                self.env.success_actions = []
                task_had_retry = False

                print(f"Running task {task_name} with instruction: {instruction}")
                print("="*15, "Raw Actions (Pretty-Printed)", "="*15)

                for action_string in self.env.raw_actions:
                    try:
                        parsed_json = json.loads(action_string)
                        pretty_json_string = json.dumps(parsed_json, indent=4)
                        print(pretty_json_string)
                        print("---")
                    except json.JSONDecodeError:
                        print("Error: JSON 파싱에 실패했습니다.")
                        print(action_string)
                print("="*58)

                with open(task_log_path, 'w', encoding='utf-8') as f_task:
                    if PRINT_ON_FILE:
                        sys.stdout = f_task
                    # [핵심 수정] 태스크 단위 예외 처리 시작
                    try:
                        while True:
                            # 리트라이 없이 단 1회만 실행
                            result: AgentInteractionResult = self.agent.step()
                            current_step_idx = step
                            step += 1

                            step_success = self.env.success_actions[-1] if self.env.success_actions else 0
                            # 리트라이 변수 업데이트 (리트라이 로직 제거로 항상 retry_used는 False)
                            step_retry_used = getattr(result.data, 'retry_count', 0) > 0
                            if step_retry_used:
                                self.action_attempts_with_retry += 1
                                self.action_success_with_retry += step_success
                                task_had_retry = True
                            else:
                                self.action_attempts_without_retry += 1
                                self.action_success_without_retry += step_success

                            print("current success actions:", self.env.success_actions)

                            if result.done:
                                task = {
                                    "instruction": instruction,
                                    "success": result.success,
                                    "step": current_step_idx,
                                    "max_step": max_step
                                }
                                results.append(task)
                                if task_had_retry:
                                    self.task_attempts_with_retry += 1
                                    if result.success:
                                        self.task_success_with_retry += 1
                                else:
                                    self.task_attempts_without_retry += 1
                                    if result.success:
                                        self.task_success_without_retry += 1
                                
                                self.total_action_len += len(self.env.success_actions)
                                self.total_success_len += sum(self.env.success_actions)

                                try:
                                    task_elapsed = time.perf_counter() - task_start_ts
                                    log_file = os.path.join(self.env.results_path, '_action_matching_log.txt')
                                    with open(log_file, 'a', encoding='utf-8') as f:
                                        f.write("\n--- Task Timing ---\n")
                                        f.write(f"app: {app_name}\n")
                                        f.write(f"task: {task_name}\n")
                                        f.write(f"instruction: {instruction}\n")
                                        f.write(f"start_time: {task_start_wall}\n")
                                        f.write(f"duration_seconds: {task_elapsed:.6f}\n")
                                        f.write(f"success: {result.success}\n")
                                        f.write(f"steps_taken: {current_step_idx} / max_step: {max_step}\n")
                                except Exception:
                                    pass

                                self.total_instruction += 1
                                if(len(self.env.success_actions) == sum(self.env.success_actions)) and result.success:
                                    self.success_instruction += 1
                                
                                if self.total_instruction > 0 and self.total_instruction % 10 == 0:
                                    if self.total_action_len > 0:
                                        elapsed = time.perf_counter() - benchmark_start_ts
                                        print("\n" + "="*25)
                                        print(f" ({self.total_instruction} complete) \n")
                                        print(f" task action success rate: {self.total_success_len}/{self.total_action_len} = {self.total_success_len / self.total_action_len:.2%}")
                                        print(f" task instruction success rate: {self.success_instruction}/{self.total_instruction} = {self.success_instruction / self.total_instruction:.2%}")
                                        print(f" action success (with retry): {_format_rate(self.action_success_with_retry, self.action_attempts_with_retry)}")
                                        print(f" action success (without retry): {_format_rate(self.action_success_without_retry, self.action_attempts_without_retry)}")
                                        print(f" task success (with retry): {_format_rate(self.task_success_with_retry, self.task_attempts_with_retry)}")
                                        print(f" task success (without retry): {_format_rate(self.task_success_without_retry, self.task_attempts_without_retry)}")
                                        print(f" elapsed time so far: {elapsed:.2f} seconds (started at {benchmark_start_wall})")
                                        print("="*25 + "\n")

                                        with open(os.path.join(self.env.results_path, "response.txt"), 'a', encoding='utf-8') as f:
                                            f.write(f"\n------- ({self.total_instruction} complete ---\n")
                                            f.write(f"task action success rate: {self.total_success_len}/{self.total_action_len} = {self.total_success_len / self.total_action_len:.2%}\n")
                                            f.write(f"task instruction success rate: {self.success_instruction}/{self.total_instruction} = {self.success_instruction / self.total_instruction:.2%}\n")
                                            f.write(f"action success (with retry): {_format_rate(self.action_success_with_retry, self.action_attempts_with_retry)}\n")
                                            f.write(f"action success (without retry): {_format_rate(self.action_success_without_retry, self.action_attempts_without_retry)}\n")
                                            f.write(f"task success (with retry): {_format_rate(self.task_success_with_retry, self.task_attempts_with_retry)}\n")
                                            f.write(f"task success (without retry): {_format_rate(self.task_success_without_retry, self.task_attempts_without_retry)}\n")
                                            f.write(f"elapsed time (seconds): {elapsed:.2f}\n")

                                with open(os.path.join(self.env.results_path, f"_action_matching_log.txt"), 'a', encoding='utf-8') as f:
                                    f.write(f"Task: {task_name}, Instruction: {instruction}, Success: {result.success}, Steps: {current_step_idx}, Max Step: {max_step}\n\n")
                                
                                gc.collect()
                                break

                    except Exception as e:
                        # [중단 방지] 에러 발생 시 로그 기록 후 다음 태스크로 건너뜀
                        print(f"\n[치명적 에러] 태스크 '{task_name}' 수행 중 오류 발생: {e}")
                        print("해당 태스크를 실패 처리하고 다음 태스크로 넘어갑니다.")
                        
                        self.total_instruction += 1
                        results.append({
                            "instruction": instruction,
                            "success": False,
                            "error": str(e)
                        })
                        
                        with open(os.path.join(self.env.results_path, f"_action_matching_log.txt"), 'a', encoding='utf-8') as f:
                            f.write(f"Task: {task_name} CRASHED with error: {e}\n\n")
                        
                        gc.collect()
                        continue
                    
                    finally:
                        sys.stdout = original_stdout

            with open(os.path.join(self.env.results_path, "response.txt"), 'a', encoding='utf-8') as f:
                f.write(f"{app_name} completed.\n")
                f.write(f"Accumulated action success rate: {self.total_success_len}/{self.total_action_len} = {self.total_success_len / self.total_action_len:.2%}\n")
                if self.total_instruction > 0:
                    f.write(f"Accumulated success instructions: {self.success_instruction}/{self.total_instruction} = {self.success_instruction / self.total_instruction:.2%}\n")
                else:
                    f.write(f"Accumulated success instructions: {self.success_instruction}/{self.total_instruction} (N/A)\n")
            gc.collect()

        total_duration = time.perf_counter() - benchmark_start_ts
        print("Benchmark completed.")
        print(f"Total elapsed time: {total_duration:.2f} seconds (started at {benchmark_start_wall})")
        print(f"Total action success rate: {self.total_success_len}/{self.total_action_len} = {self.total_success_len / self.total_action_len:.2%}")
        if self.total_instruction > 0:
            print(f"Total success instructions: {self.success_instruction}/{self.total_instruction} = {self.success_instruction / self.total_instruction:.2%}")
        else:
            print(f"Total success instructions: {self.success_instruction}/{self.total_instruction} (N/A)")
        print(f"Action success (with retry): {_format_rate(self.action_success_with_retry, self.action_attempts_with_retry)}")
        print(f"Action success (without retry): {_format_rate(self.action_success_without_retry, self.action_attempts_without_retry)}")
        print(f"Task success (with retry): {_format_rate(self.task_success_with_retry, self.task_attempts_with_retry)}")
        print(f"Task success (without retry): {_format_rate(self.task_success_without_retry, self.task_attempts_without_retry)}")

        with open(os.path.join(self.env.results_path, "response.txt"), 'a', encoding='utf-8') as f:
            f.write("Benchmark completed.\n")
            f.write(f"Benchmark start: {benchmark_start_wall}\n")
            f.write(f"Total elapsed time (seconds): {total_duration:.2f}\n")
            f.write(f"Total action success rate: {self.total_success_len}/{self.total_action_len} = {self.total_success_len / self.total_action_len:.2%}\n")
            if self.total_instruction > 0:
                f.write(f"Total success instructions: {self.success_instruction}/{self.total_instruction} = {self.success_instruction / self.total_instruction:.2%}\n")
            else:
                f.write(f"Total success instructions: {self.success_instruction}/{self.total_instruction} (N/A)\n")
            f.write(f"Action success (with retry): {_format_rate(self.action_success_with_retry, self.action_attempts_with_retry)}\n")
            f.write(f"Action success (without retry): {_format_rate(self.action_success_without_retry, self.action_attempts_without_retry)}\n")
            f.write(f"Task success (with retry): {_format_rate(self.task_success_with_retry, self.task_attempts_with_retry)}\n")
            f.write(f"Task success (without retry): {_format_rate(self.task_success_without_retry, self.task_attempts_without_retry)}\n")