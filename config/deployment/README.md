# Safe monitor deployment — NOT live commerce

Files only: no task has been installed and no process has been started by this change.
Do not register until the parent verifies `main.py --mode full --read-only` is accepted
and the process-lifetime read-only override blocks EVERY remote commerce write even
when .env is changed to enable writes. No supplier agreement, business approval or
verified payment readiness is implied. Never remove `--read-only` to make startup work.

## Preflight (parent/operator)

1. Run the external operation tests with Python 3.11:
   `"C:\Program Files\Python311\python.exe" "C:\Users\Administrator\AppData\Local\hermes\cache\scratch\test_operations.py"`
2. Run the parent's complete guard/integration suite, including .env-toggle attempts,
   scheduled maintenance invocation, existing-log redaction at startup and no raw-log
   serving. Do not display the historical `logs/system.log`: it contains secrets.
3. Confirm no competing manual server uses loopback port 5000. Do not expose dashboard
   beyond loopback. Verify paths/user identity and protect backup/state directories with
   a private Windows ACL (Python chmod is NOT a Windows ACL security guarantee).
4. XML is UTF-8, XML-escaped, with an unquoted executable field and quoted script argument.
   WorkingDirectory is explicit. Boot and Administrator logon triggers delay 1 minute;
   duplicate instances are ignored. Failed processes restart after 1 minute, at most
   3 restart attempts per failure cycle. Restart policy is not a crash-proof lifetime
   cap: subsequent triggers may start a new cycle. Exit status 0 is not a failure.
5. S4U / least privilege stores no plaintext password and supports unattended boot.
   S4U has no network credentials or access to encrypted files. This profile is for
   local safe monitoring, NOT authenticated network commerce. Windows account policy
   may require 'Log on as a batch job' or deny S4U. Treat a registration/run failure as
   a blocker; do not replace this with stored credentials or higher privileges silently.
   Parse tests do not prove Windows Task Scheduler accepts the task on this host.

## Explicit operator commands (PowerShell, not executed here)

After all preflight checks pass and deployment is authorized:

```powershell
schtasks.exe /Create /TN "Mondeora-Safe-Monitor" /XML "C:\Users\Administrator\Desktop\Mondeora-Drop-System\config\deployment\mondeora-safe-monitor.xml"
# Inspect exact registered arguments before starting. No /F: do not overwrite an existing task.
schtasks.exe /Query /TN "Mondeora-Safe-Monitor" /XML
schtasks.exe /Run /TN "Mondeora-Safe-Monitor"
# Status; a scheduler Running state is NOT proof of application health.
schtasks.exe /Query /TN "Mondeora-Safe-Monitor" /V /FO LIST
Get-ScheduledTaskInfo -TaskName 'Mondeora-Safe-Monitor'
# Persistent stop: disable future triggers, then stop current task.
schtasks.exe /Change /TN "Mondeora-Safe-Monitor" /DISABLE
schtasks.exe /End /TN "Mondeora-Safe-Monitor"
# Resume only after the same safety checks:
schtasks.exe /Change /TN "Mondeora-Safe-Monitor" /ENABLE
schtasks.exe /Run /TN "Mondeora-Safe-Monitor"
```

Read back registered XML and check exact executable, working directory, flags,
principal, triggers and restart limits. After an authorized start, verify application
health over loopback and the sanitized status timestamp advances; verify failed writes
remain blocked and task status. Stop/disable on any mismatch. Never infer health from
an old status file; compare timestamps to the last maintenance interval.

## Operations integration contract

Importing `src.operations` has no side effects; parent must wire one serialized,
independent maintenance scheduler job (e.g. hourly) into the launcher. Call:

```python
from src.operations import snapshot_database, record_status
try:
    snapshot_database(actual_database_path, private_backup_directory, retain=7)
    record_status(private_state_directory, status='ok', counts={'backups': 1})
except Exception:
    record_status(private_state_directory, status='error', counts={'errors': 1})
```

Do not pass exceptions to another logger or print them: messages may carry secrets.
`message=` is accepted but discarded completely. Counts accept only backups/errors/
orders/products/pending/blocked, with integer values 0..1,000,000,000; unknown status
maps to `unknown`. Status values: ok/degraded/error/unknown. No business record IDs,
paths, tokens, customer messages or tracebacks are serialized.

`status.json` is atomically replaced; `alerts.jsonl` is local-only, rotated to one
`alerts.jsonl.1` at 256 KiB by default. No remote alerts are configured or delivered;
there is no email connector, SMTP setup or remote-delivery success claim. Local disk
failure can prevent local alerts too: operator should monitor file freshness externally.
Do not serve raw logs as a substitute.

Backups use SQLite online backup, include committed WAL, verify integrity, close all
handles, sync before atomic publication, then retain 7 snapshots by default (1..1000).
Only strict generated snapshot filenames are retention candidates; unrelated files
and subdirectories are untouched. A 30-second backup progress deadline bounds busy
retries; slow filesystem/integrity verification are not hard real-time bounded.
`manifest.json` is atomically replaced with filenames, byte counts and SHA-256 values.
Individual files are atomic, not the entire retention/manifest transaction: if interrupted,
rerun maintenance to reconcile. Run only one maintenance caller per directory.

The default backup directory is outside the project:
`C:\Users\Administrator\Desktop\Mondeora-runtime-backups`.
No .env, log files, demo database or sample records are copied/inserted. Database backups
DO contain the actual database's records and must be kept private and encrypted by
operator policy. They are not guaranteed secret-free if secrets were stored in the DB.

Restore drill: stop/disable the application first, verify the selected manifest hash,
open a COPY of the snapshot in SQLite and run `PRAGMA integrity_check`; check expected
schema/counts without printing records. Restore into a fresh database path with no old
WAL/SHM sidecars. Never overwrite a live DB or copy old WAL sidecars over a snapshot.
Tests perform a committed-WAL restore drill using isolated synthetic fixtures only;
no real customer records are read or printed.
