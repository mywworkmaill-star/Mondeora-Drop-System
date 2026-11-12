import ast
import re

from conftest import ROOT, py_files


def test_every_python_file_compiles_without_bom():
    bad = []
    for p in py_files():
        raw = p.read_bytes()
        if raw.startswith(b'\xef\xbb\xbf'):
            bad.append((p.name, 'BOM'))
        try:
            ast.parse(raw.decode('utf-8-sig'))
        except SyntaxError as e:
            bad.append((p.name, f'syntax line {e.lineno}'))
    assert not bad, bad


def test_http_calls_have_timeouts():
    missing = []
    for p in py_files():
        try:
            tree = ast.parse(p.read_text(encoding='utf-8-sig'))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and isinstance(n.func.value, ast.Name) and n.func.value.id == 'requests'
                    and n.func.attr in {'get', 'post', 'put', 'delete', 'patch', 'head', 'request'}
                    and not any(k.arg == 'timeout' or k.arg is None for k in n.keywords)):
                missing.append(f'{p.name}:{n.lineno}')
    assert not missing, missing


def test_xml_parsing_uses_defusedxml():
    offenders = [f'{p.name}:{i}' for p in py_files()
                 for i, line in enumerate(p.read_text(encoding='utf-8-sig').splitlines(), 1)
                 if re.search(r'\bET\.fromstring\(', line)]
    assert not offenders, offenders


def test_no_real_looking_ebay_tokens_in_tracked_sources():
    pattern = re.compile(r'v\^1\.1#[A-Za-z0-9^#_=\-]{40,}')
    offenders = []
    for p in list(py_files()) + [ROOT / 'INSTALLATION.md']:
        if p.exists() and pattern.search(p.read_text(encoding='utf-8-sig', errors='replace')):
            offenders.append(p.name)
    assert not offenders, offenders


def test_env_files_are_gitignored():
    ignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
    for entry in ('.env', '*.db', 'tokens.json'):
        assert entry in ignore
