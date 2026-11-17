"""Read-only, standard-library checks for code, configuration and general docs."""

import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
INLINE_LINK = re.compile(r'\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s)]+))(?:\s+"[^"\n]*")?\s*\)')


def repository_files(root):
    """Include new, non-ignored files so local and CI checks have the same scope."""
    result = subprocess.run(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
        cwd=root, check=True, stdout=subprocess.PIPE,
    )
    return sorted(set(result.stdout.decode('utf-8').strip('\0').split('\0')) - {''})


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f'non-standard JSON constant: {value}')


def markdown_links(text):
    """Extract inline links/images outside fenced blocks and inline code.

    This is deliberately not a full Markdown parser. Reference links, HTML,
    nested parentheses in destinations and heading anchors are outside scope.
    """
    fence = None
    for line in text.splitlines():
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            line = re.sub(r'(`+).*?\1', '', line)
            for match in INLINE_LINK.finditer(line):
                yield match[1] if match[1] is not None else match[2]


def check_file(root, relative):
    path = root / relative
    is_python = path.suffix == '.py'
    is_config = relative.startswith('config/') and path.suffix == '.json'
    is_document = path.suffix == '.md' and ('/' not in relative or relative.startswith('docs/'))
    if not (is_python or is_config or is_document):
        return None, []
    kind = 'python' if is_python else 'json' if is_config else 'docs'
    try:
        text = path.read_text(encoding='utf-8')
        if is_python:
            compile(text, relative, 'exec', dont_inherit=True)
        elif is_config:
            json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
        else:
            errors = []
            for target in markdown_links(text):
                url = urlsplit(target)
                if url.scheme or url.netloc or not url.path:
                    continue
                destination = (path.parent / unquote(url.path)).resolve()
                if not destination.is_relative_to(root.resolve()) or not destination.exists():
                    errors.append(f'{relative}: missing or outside-checkout link: {target}')
            return kind, errors
    except (OSError, UnicodeError, SyntaxError, ValueError) as error:
        return kind, [f'{relative}: {error}']
    return kind, []


def main():
    counts = dict.fromkeys(('python', 'json', 'docs'), 0)
    errors = []
    try:
        for relative in repository_files(ROOT):
            kind, failures = check_file(ROOT, relative)
            if kind:
                counts[kind] += 1
            errors.extend(failures)
    except (OSError, subprocess.CalledProcessError, UnicodeError) as error:
        errors.append(str(error))
    print('Infrastructure:', ', '.join(f'{kind}={count}' for kind, count in counts.items()))
    for error in errors:
        print(error, file=sys.stderr)
    print(f'Infrastructure: {len(errors)} error(s)')
    return bool(errors)


if __name__ == '__main__':
    sys.exit(main())
