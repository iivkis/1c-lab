#!/usr/bin/env python3
"""Fail CI only for BSL parse errors; verify the requested files were analyzed."""
import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


def main() -> int:
    if len(sys.argv) != 3:
        print('Usage: check-bsl-report.py REPORT_JSON SOURCE_DIR', file=sys.stderr)
        return 2
    report, source_dir = map(Path, sys.argv[1:])
    expected = {p.resolve() for p in source_dir.rglob('*.bsl') if p.is_file()}
    if not expected:
        print('ERROR: no .bsl files in src/', file=sys.stderr)
        return 1
    try:
        data = json.loads(report.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'ERROR: cannot read BSL analysis report: {exc}', file=sys.stderr)
        return 1
    infos = data.get('fileinfos')
    if not isinstance(infos, list):
        print('ERROR: invalid BSL analysis report: fileinfos missing', file=sys.stderr)
        return 1

    analyzed = set()
    errors = []
    for info in infos:
        raw_path = str(info.get('path', ''))
        parsed = urlsplit(raw_path)
        path = Path(unquote(parsed.path) if parsed.scheme == 'file' else raw_path).resolve()
        analyzed.add(path)
        for diag in info.get('diagnostics', []):
            if str(diag.get('code', '')).replace('Diagnostic', '') != 'ParseError':
                continue
            start = diag.get('range', {}).get('start', {})
            line = int(start.get('line', 0)) + 1
            col = int(start.get('character', 0)) + 1
            msg = str(diag.get('message', 'BSL syntax error'))
            errors.append((path, line, col, msg))

    missing = expected - analyzed
    if missing:
        for path in sorted(missing):
            print(f'ERROR: BSL Language Server did not analyze {path}', file=sys.stderr)
        return 1
    for path, line, col, msg in errors:
        escaped = msg.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print(f'::error file={path},line={line},col={col}::{escaped}')
    if errors:
        print(f'FAIL: {len(errors)} BSL syntax error(s) in {len(expected)} file(s).')
        return 1
    print(f'PASS: {len(expected)} BSL file(s) parsed successfully (ParseError = 0).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
