"""python -m hvac_engine input.json --output result.json"""
import argparse
import json
import sys
from pathlib import Path
from . import calculate_project, InputError


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='HVAC顯式逐時負荷計算基礎')
    parser.add_argument('input')
    parser.add_argument('--output')
    args = parser.parse_args()
    try:
        result = calculate_project(json.loads(Path(args.input).read_text(encoding='utf-8-sig')))
        content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            Path(args.output).write_text(content + '\n', encoding='utf-8')
        else:
            print(content)
    except (InputError, OSError, json.JSONDecodeError) as exc:
        print(f'計算未完成：{exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
