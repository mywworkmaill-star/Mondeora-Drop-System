"""Safe-monitor Task Scheduler preview/explicit idempotent activation.

No registration, start, credential use or host-setting change on import/preview.
Activation installs only; the first task run and reboot remain operator actions.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from defusedxml.ElementTree import fromstring as _safe_fromstring

ROOT = Path(__file__).resolve().parents[1]
XML_PATH = ROOT / 'config/deployment/mondeora-safe-monitor.xml'
TASK_NAME = 'Mondeora-Safe-Monitor'
NS = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}


def _contract(text):
    tree = _safe_fromstring(text)
    paths = {'command': 't:Actions/t:Exec/t:Command',
             'arguments': 't:Actions/t:Exec/t:Arguments',
             'working_directory': 't:Actions/t:Exec/t:WorkingDirectory',
             'principal': 't:Principals/t:Principal/t:UserId',
             'logon_type': 't:Principals/t:Principal/t:LogonType',
             'run_level': 't:Principals/t:Principal/t:RunLevel',
             'duplicates': 't:Settings/t:MultipleInstancesPolicy',
             'restart_interval': 't:Settings/t:RestartOnFailure/t:Interval',
             'restart_attempts': 't:Settings/t:RestartOnFailure/t:Count'}
    result: dict = {key: tree.findtext(path, default='', namespaces=NS) for key, path in paths.items()}
    result['action_count'] = len(tree.findall('t:Actions/*', NS))
    result['enabled'] = tree.findtext('t:Settings/t:Enabled', default='', namespaces=NS)
    result['triggers'] = [{'type': item.tag.rsplit('}', 1)[-1],
        **{child.tag.rsplit('}', 1)[-1]: (child.text or '').strip() for child in item}}
        for item in tree.findall('t:Triggers/*', NS)]
    return result


def startup_preview():
    data = _contract(XML_PATH.read_text(encoding='utf-8-sig'))
    expected = f'"{ROOT / "main.py"}" --mode full --read-only'
    if (Path(data['command']) != Path('C:/Program Files/Python311/python.exe')
        or not Path(data['command']).is_file()
        or data['arguments'] != expected
        or Path(data['working_directory']) != ROOT
        or data['principal'] != 'Administrator'
        or data['logon_type'] != 'S4U' or data['run_level'] != 'LeastPrivilege'
        or data['duplicates'] != 'IgnoreNew'
        or data['restart_interval'] != 'PT1M' or data['restart_attempts'] != '3'
        or data['action_count'] != 1 or data['enabled'] != 'true'
        or data['triggers'] != [
            {'type': 'BootTrigger', 'Enabled': 'true', 'Delay': 'PT1M'},
            {'type': 'LogonTrigger', 'Enabled': 'true', 'Delay': 'PT1M', 'UserId': 'Administrator'}]):
        raise ValueError('Unexpected safe-monitor task contract')
    return {**data, 'restart_attempts': 3, 'read_only': True,
            'activation': 'approval_required', 'registered': False,
            'reboot_verified': False, 'windows_registration_verified': False,
            'xml': str(XML_PATH),
            'activate_command': subprocess.list2cmdline([str(Path(data['command'])), '-m',
                'src.deployment', '--activate']),
            'first_run_command': f'schtasks.exe /Run /TN "{TASK_NAME}"',
            'scope': 'local monitor; no publication, purchase, payment or remote alerts'}


def _account_key(value):
    """Task Scheduler canonicalizes account names to SIDs on XML readback."""
    if value.startswith('S-1-'):
        return value.casefold()
    import ctypes
    from ctypes import wintypes
    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    lookup = advapi.LookupAccountNameW
    lookup.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
    lookup.restype = wintypes.BOOL
    size, domain_size, kind = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
    lookup(None, value, None, ctypes.byref(size), None, ctypes.byref(domain_size), ctypes.byref(kind))
    if not size.value:
        raise ValueError('Task principal cannot be resolved')
    sid = ctypes.create_string_buffer(size.value)
    domain = ctypes.create_unicode_buffer(domain_size.value)
    if not lookup(None, value, sid, ctypes.byref(size), domain, ctypes.byref(domain_size), ctypes.byref(kind)):
        raise ValueError('Task principal cannot be resolved')
    convert = advapi.ConvertSidToStringSidW
    convert.argtypes = [wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR)]
    convert.restype = wintypes.BOOL
    text = wintypes.LPWSTR()
    if not convert(sid, ctypes.byref(text)):
        raise ValueError('Task principal SID cannot be resolved')
    try:
        return text.value.casefold()
    finally:
        free = ctypes.WinDLL('kernel32').LocalFree
        free.argtypes = [wintypes.LPVOID]
        free.restype = wintypes.LPVOID
        free(ctypes.cast(text, wintypes.LPVOID))


def _registered_contract(text):
    contract = _contract(text)
    contract['principal'] = _account_key(contract['principal'])
    for trigger in contract['triggers']:
        if trigger.get('UserId'):
            trigger['UserId'] = _account_key(trigger['UserId'])
    return contract


def activate():
    """No /F: never overwrite a conflicting task. Always read back exact target."""
    preview = startup_preview()
    if os.name != 'nt':
        raise RuntimeError('Windows required')
    def query():
        return subprocess.run(['schtasks.exe', '/Query', '/TN', TASK_NAME, '/XML'],
            capture_output=True, text=True, timeout=30)
    current = query()
    expected = _registered_contract(XML_PATH.read_text(encoding='utf-8-sig'))
    if current.returncode == 0:
        if _registered_contract(current.stdout) != expected:
            raise RuntimeError('Existing task differs; no overwrite performed')
        outcome = 'already_registered'
    else:
        created = subprocess.run(['schtasks.exe', '/Create', '/TN', TASK_NAME,
            '/XML', str(XML_PATH)], capture_output=True, text=True, timeout=30)
        if created.returncode:
            raise RuntimeError('Task registration failed; inspect local Task Scheduler policy')
        outcome = 'registered'
    verified = query()
    if verified.returncode or _registered_contract(verified.stdout) != expected:
        raise RuntimeError('Task readback mismatch; do not run task')
    return {**preview, 'activation': outcome, 'registered': True,
            'windows_registration_verified': True, 'started': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Safe monitor startup: preview is default')
    parser.add_argument('--activate', action='store_true', help='Explicit approval to register persistent task; does not start it')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(activate() if args.activate else startup_preview(), indent=2))
        return 0
    except Exception as exc:
        print('Deployment failed (' + type(exc).__name__ + '); no unattended acceptance claimed.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
