"""CI lint gate: fail when pylint reports more messages than scripts/pylint_baseline.json allows.

The codebase isn't pylint-clean yet (`.pylintrc` asks for a 10/10 score), so this blocks regressions instead of
requiring zero messages. It counts pylint's messages per file and message type, and compares them to the baseline:
- A count above its baseline fails, because new code added a message. Fix it, or disable it inline with a reason.
- A count below its baseline also fails, so the baseline only ever shrinks. Rerun with --update-baseline and commit
  the result.
Counts are compared instead of line numbers, so edits that only move code around don't matter.

The baseline records CI's environment: Linux, with requirements-dev.txt installed. Messages that depend on which
optional packages are installed are configured away in .pylintrc (see ignored-modules).

Usage: python scripts/pylint_check.py [--update-baseline]
"""
import argparse
import json
import os
import subprocess
import sys
from collections import Counter

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE_PATH = os.path.join(PROJECT_DIR, 'scripts', 'pylint_baseline.json')
PYLINT_USAGE_ERROR = 32

# pylint reports each of these against one of the files involved, picked by the order it reads files in, which
# differs between filesystems. They're counted once for the whole repository instead.
REPOSITORY_WIDE_SYMBOLS = {'duplicate-code'}
REPOSITORY_WIDE_PATH = '(repository)'


def run_pylint() -> list[dict]:
    """Runs pylint over src/ and returns its messages."""
    result = subprocess.run([sys.executable, '-m', 'pylint', '--rcfile=.pylintrc', '--output-format=json2', 'src'],
                            cwd=PROJECT_DIR, capture_output=True, text=True, check=False)
    # pylint's exit status is a bit field of the message categories it found; only a usage error means no report.
    if result.returncode & PYLINT_USAGE_ERROR or not result.stdout:
        sys.exit(f'pylint failed to run (exit status {result.returncode}):\n{result.stderr}')
    return json.loads(result.stdout)['messages']


def message_path(message: dict) -> str:
    """Returns the path a pylint message is counted under."""
    if message['symbol'] in REPOSITORY_WIDE_SYMBOLS:
        return REPOSITORY_WIDE_PATH
    return message['path'].replace(os.sep, '/')


def count_messages(messages: list[dict]) -> dict[str, dict[str, int]]:
    """Returns {path: {message symbol: count}}, sorted for a stable baseline file."""
    counts: dict[str, Counter] = {}
    for message in messages:
        counts.setdefault(message_path(message), Counter())[message['symbol']] += 1
    return {path: dict(sorted(counter.items())) for path, counter in sorted(counts.items())}


def main() -> None:
    """Compares pylint's message counts to the baseline, or rewrites the baseline."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n', maxsplit=1)[0])
    parser.add_argument('--update-baseline', action='store_true',
                        help='Write the current message counts to the baseline file instead of checking them.')
    args = parser.parse_args()

    messages = run_pylint()
    current = count_messages(messages)
    if args.update_baseline:
        with open(BASELINE_PATH, 'w', encoding='utf-8') as baseline_file:
            json.dump(current, baseline_file, indent=2)
            baseline_file.write('\n')
        print(f'Wrote {len(messages)} messages in {len(current)} files to {os.path.relpath(BASELINE_PATH)}.')
        return

    with open(BASELINE_PATH, encoding='utf-8') as baseline_file:
        baseline: dict[str, dict[str, int]] = json.load(baseline_file)
    added = 0
    removed = 0
    for path in sorted(set(current) | set(baseline)):
        path_counts = current.get(path, {})
        path_baseline = baseline.get(path, {})
        for symbol in sorted(set(path_counts) | set(path_baseline)):
            count = path_counts.get(symbol, 0)
            allowed = path_baseline.get(symbol, 0)
            if count > allowed:
                added += count - allowed
                print(f'{path}: {count} {symbol} message(s), baseline allows {allowed}. At least one of these is new:')
                for message in messages:
                    if message_path(message) == path and message['symbol'] == symbol:
                        print(f'    {message["path"]}:{message["line"]}:{message["column"]}: {message["message"]}')
            elif count < allowed:
                removed += allowed - count
                print(f'{path}: {count} {symbol} message(s), baseline allows {allowed}.')
    if added > 0:
        print(f'\npylint found {added} new message(s). Fix them, or disable them inline with a reason.')
    if removed > 0:
        print(f'\n{removed} baseline message(s) are fixed. Run `python scripts/pylint_check.py --update-baseline` '
              'and commit scripts/pylint_baseline.json to lock that in.')
    if added > 0 or removed > 0:
        sys.exit(1)
    print(f'pylint: {len(messages)} messages, all within the baseline.')


if __name__ == '__main__':
    main()
