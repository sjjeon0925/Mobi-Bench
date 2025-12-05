import re
import sys
from pathlib import Path


def sum_totals(path: Path):
    """
    Sums token usage across a divandconq response log.
    - Reports both native_* tokens (post-caching) and tokens_* (pre-caching).
    - Also counts completion image tokens and cached tokens when present.
    """
    total_cost = 0.0
    native_prompt_tokens = 0
    native_completion_tokens = 0
    native_completion_images = 0
    native_reasoning_tokens = 0
    native_cached_tokens = 0

    prompt_tokens = 0
    completion_tokens = 0

    call_count = 0

    cost_pattern = re.compile(r'"total_cost"\s*:\s*([0-9.]+)')
    native_prompt_pattern = re.compile(r'"native_tokens_prompt"\s*:\s*(\d+)')
    native_completion_pattern = re.compile(r'"native_tokens_completion"\s*:\s*(\d+)')
    native_completion_images_pattern = re.compile(r'"native_tokens_completion_images"\s*:\s*(\d+)')
    native_reasoning_pattern = re.compile(r'"native_tokens_reasoning"\s*:\s*(\d+)')
    native_cached_pattern = re.compile(r'"native_tokens_cached"\s*:\s*(\d+)')

    prompt_pattern = re.compile(r'"tokens_prompt"\s*:\s*(\d+)')
    completion_pattern = re.compile(r'"tokens_completion"\s*:\s*(\d+)')

    with path.open(encoding="utf-8") as f:
        for line in f:
            # Quick check: count only lines with a "generation" block to avoid headers
            if '"generation"' in line or '"total_cost"' in line:
                call_count += 1
            if match := cost_pattern.search(line):
                total_cost += float(match.group(1))
            if match := native_prompt_pattern.search(line):
                native_prompt_tokens += int(match.group(1))
            if match := native_completion_pattern.search(line):
                native_completion_tokens += int(match.group(1))
            if match := native_completion_images_pattern.search(line):
                native_completion_images += int(match.group(1))
            if match := native_reasoning_pattern.search(line):
                native_reasoning_tokens += int(match.group(1))
            if match := native_cached_pattern.search(line):
                native_cached_tokens += int(match.group(1))
            if match := prompt_pattern.search(line):
                prompt_tokens += int(match.group(1))
            if match := completion_pattern.search(line):
                completion_tokens += int(match.group(1))

    return {
        "calls": call_count,
        "total_cost": total_cost,
        "native_prompt_tokens": native_prompt_tokens,
        "native_completion_tokens": native_completion_tokens,
        "native_completion_image_tokens": native_completion_images,
        "native_reasoning_tokens": native_reasoning_tokens,
        "native_cached_tokens": native_cached_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }


def main():
    args = sys.argv[1:]
    if not args:
        user_input = input("Enter path(s) to response.txt (space-separated): ").strip()
        if not user_input:
            print("Usage: python sum_total_cost.py <response1> [response2 ...]")
            sys.exit(1)
        args = user_input.split()
    paths = [Path(p) for p in args]

    grand = {
        "calls": 0,
        "total_cost": 0.0,
        "native_prompt_tokens": 0,
        "native_completion_tokens": 0,
        "native_completion_image_tokens": 0,
        "native_reasoning_tokens": 0,
        "native_cached_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }

    for path in paths:
        if not path.is_file():
            print(f"[WARN] File not found: {path}")
            continue
        totals = sum_totals(path)
        print(f"{path}:")
        print(f"  Calls: {totals['calls']}")
        print(f"  Total cost: {totals['total_cost']}")
        print(f"  Total native prompt tokens: {totals['native_prompt_tokens']}")
        print(f"  Total native completion tokens: {totals['native_completion_tokens']}")
        print(f"    - Native completion image tokens: {totals['native_completion_image_tokens']}")
        print(f"    - Native reasoning tokens: {totals['native_reasoning_tokens']}")
        print(f"    - Native cached tokens: {totals['native_cached_tokens']}")
        print(f"  Total tokens_prompt (pre-cache): {totals['prompt_tokens']}")
        print(f"  Total tokens_completion (pre-cache): {totals['completion_tokens']}")
        print()
        for k in grand:
            grand[k] += totals[k]

    if len(paths) > 1:
        print("GRAND TOTAL:")
        print(f"  Calls: {grand['calls']}")
        print(f"  Total cost: {grand['total_cost']}")
        print(f"  Total native prompt tokens: {grand['native_prompt_tokens']}")
        print(f"  Total native completion tokens: {grand['native_completion_tokens']}")
        print(f"    - Native completion image tokens: {grand['native_completion_image_tokens']}")
        print(f"    - Native reasoning tokens: {grand['native_reasoning_tokens']}")
        print(f"    - Native cached tokens: {grand['native_cached_tokens']}")
        print(f"  Total tokens_prompt (pre-cache): {grand['prompt_tokens']}")
        print(f"  Total tokens_completion (pre-cache): {grand['completion_tokens']}")


if __name__ == "__main__":
    main()
