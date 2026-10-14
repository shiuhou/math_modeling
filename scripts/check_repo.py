#!/usr/bin/env python3
"""Check local inline Markdown link paths and strict JSON syntax; Python 3.10+."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


LINK = re.compile(r'!?\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s()]+))(?:\s+"[^"\n]*")?\s*\)')


def link_targets(content: str):
    """Yield (line, destination), excluding fenced blocks and inline code.

    This intentionally checks inline links, not reference-style links or anchors.
    Destinations containing spaces/parentheses must use Markdown's <...> form.
    """
    fence = None
    for number, line in enumerate(content.splitlines(), 1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if marker:
            token, suffix = marker.groups()
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not suffix.strip():
                fence = None
            continue
        if fence is not None or line.startswith(("    ", "\t")):
            continue
        line = re.sub(r"(`+).*?\1", "", line)
        for match in LINK.finditer(line):
            yield number, match.group(1) or match.group(2)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f"non-finite JSON value: {value}")


def repository_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root, capture_output=True, check=True,
    )
    return sorted({Path(p.decode("utf-8")) for p in result.stdout.split(b"\0") if p})


def check_files(root: Path, files: list[Path]) -> list[str]:
    root = root.resolve()
    included = {(root / p).resolve() for p in files if (root / p).is_file()}
    # A linked directory must contain included content, not only ignored files.
    directories = {parent for p in included for parent in p.parents if parent.is_relative_to(root)}
    errors = []
    for relative in files:
        path = root / relative
        if not path.is_file() or path.suffix.lower() not in {".md", ".json"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
            if path.suffix.lower() == ".json":
                json.loads(content, object_pairs_hook=unique_object, parse_constant=reject_constant)
                continue
            for number, destination in link_targets(content):
                url = urlsplit(destination)
                if url.scheme or url.netloc or not url.path:
                    continue
                local = unquote(url.path)
                target = (path.parent / local).resolve()
                if local.startswith("/") or not target.is_relative_to(root):
                    errors.append(f"{relative}:{number}: link leaves repository: {destination}")
                elif target not in included and target not in directories:
                    errors.append(f"{relative}:{number}: missing or ignored link target: {destination}")
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{relative}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        files = repository_files(args.root)
        errors = check_files(args.root, files)
    except (OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: unable to inspect repository: {exc}", file=sys.stderr)
        return 1
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    count = sum((args.root / p).is_file() and p.suffix.lower() in {".md", ".json"} for p in files)
    print(f"PASS: local inline Markdown link paths and JSON syntax ({count} files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
