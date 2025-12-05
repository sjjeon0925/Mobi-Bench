import sys
from pathlib import Path


def analyze_log(path: Path) -> int:
    failures = 0
    steps = []
    current_type = None
    current_result = None
    task_summary = []

    def commit_step():
        nonlocal current_type, current_result
        if current_type is not None and current_result is not None:
            steps.append((current_type, current_result))
        current_type = None
        current_result = None

    with path.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            stripped = line.strip()

            if stripped.startswith("-> Type Match:") and current_type is None:
                lowered = stripped.lower()
                if "openapp" in lowered:
                    current_type = "openapp"
                elif "finish" in lowered:
                    current_type = "finish"
                else:
                    current_type = "other"

            if stripped.startswith("Final Matching Result:"):
                current_result = "True" in stripped

            if stripped == "" or stripped.startswith("==============================") or stripped.startswith("--- Task Timing ---"):
                commit_step()
            if stripped.startswith("Task: "):
                if steps:
                    first = steps[0]
                    rest = steps[1:]
                    if (
                        first[0] == "openapp"
                        and not first[1]
                        and all(result for _, result in rest)
                    ):
                        failures += 1
                steps = []

    return failures


def main():
    if len(sys.argv) < 2:
        print("Usage: python find_openapp_first_only_fail.py <log1> [<log2> ...]")
        sys.exit(1)

    total_failures = 0
    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.is_file():
            print(f"File not found: {path}")
            continue
        failures = analyze_log(path)
        print(f"{path}: {failures} tasks where only first-step openapp failed")
        total_failures += failures

    if len(sys.argv) > 2:
        print(f"TOTAL: {total_failures} tasks")


if __name__ == "__main__":
    main()
