import sys
from pathlib import Path


def count_matches(path: Path) -> tuple[int, int]:
    finish_matches = 0
    openapp_matches = 0
    loop_openapp = False

    with path.open(encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("-> Type Match:"):
                if "'finish'" in stripped:
                    finish_matches += 1
                elif "'openapp'" in stripped:
                    openapp_matches += 1

    return finish_matches, openapp_matches


def main():
    if len(sys.argv) < 2:
        print("Usage: python count_action_matches.py <log1> [<log2> ...]")
        sys.exit(1)

    total_finish = 0
    total_openapp = 0
    divisor = 484

    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.is_file():
            print(f"File not found: {path}")
            continue
        finish, openapp = count_matches(path)
        total_finish += finish
        total_openapp += openapp
        print(f"{path}: finish matches={finish} ({finish/divisor:.4f}), openapp matches={openapp} ({openapp/divisor:.4f})")

    if len(sys.argv) > 2:
        print(f"TOTAL: finish matches={total_finish} ({total_finish/divisor:.4f}), "
              f"openapp matches={total_openapp} ({total_openapp/divisor:.4f})")


if __name__ == "__main__":
    main()
