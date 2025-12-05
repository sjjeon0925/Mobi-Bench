import sys
from pathlib import Path


def find_openapp_failures(path: Path) -> list[str]:
    failures = []
    current_block: list[str] = []
    predicted_openapp = False
    final_result = None
    block_ready = False

    with path.open(encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.rstrip('\n')
            current_block.append(line)

            if 'openapp' in line.lower():
                predicted_openapp = True

            if 'Final Matching Result:' in line:
                final_result = 'False' if 'False' in line else 'True'
                block_ready = True

            if not line.strip() and block_ready:
                if predicted_openapp and final_result == 'False':
                    failures.append("\n".join(current_block).strip())
                current_block = []
                predicted_openapp = False
                final_result = None
                block_ready = False

    if block_ready and predicted_openapp and final_result == 'False':
        failures.append("\n".join(current_block).strip())

    return failures


def main():
    if len(sys.argv) < 2:
        print("Usage: python find_openapp_failures.py <log1> [<log2> ...]")
        sys.exit(1)

    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.is_file():
            print(f"File not found: {path}")
            continue
        failures = find_openapp_failures(path)
        print(f"{path}: {len(failures)} openapp failures")
        for idx, block in enumerate(failures, 1):
            print(f"\n--- Failure {idx} ---")
            print(block)
            print("--- end ---")


if __name__ == "__main__":
    main()
