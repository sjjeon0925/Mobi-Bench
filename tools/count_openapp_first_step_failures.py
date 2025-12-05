import sys
from pathlib import Path


def count_failures(path: Path) -> int:
    failures = 0
    first_type = None
    final_result = None

    def commit():
        nonlocal failures, first_type, final_result
        if first_type == 'openapp' and final_result is False:
            failures += 1
        first_type = None
        final_result = None

    with path.open(encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("-> Type Match:") and first_type is None:
                if "'openapp'" in stripped:
                    first_type = 'openapp'
                else:
                    first_type = 'other'
            if stripped.startswith("Final Matching Result:"):
                final_result = "False" in stripped
            if not stripped:
                commit()

    commit()
    return failures


def main():
    if len(sys.argv) < 2:
        print("Usage: python count_openapp_first_step_failures.py <log1> [<log2> ...]")
        sys.exit(1)

    total = 0
    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.is_file():
            print(f"File not found: {path}")
            continue
        failures = count_failures(path)
        total += failures
        print(f"{path}: first-step openapp failures={failures}")

    if len(sys.argv) > 2:
        print(f"TOTAL: first-step openapp failures={total}")


if __name__ == "__main__":
    main()
