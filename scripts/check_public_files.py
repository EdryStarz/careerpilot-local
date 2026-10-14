"""Check the publication set for obvious private runtime artifacts and tokens."""
import re
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
errors = []
for name in paths:
    path = ROOT / name
    if not path.is_file():
        continue
    if path.name in {'.env', 'profile.yaml', 'careerpilot.yaml', 'last-run.json', 'jobs.json', '.profile-owner', 'application_answers.json', 'work_preferences.json'} or path.name.startswith(('proof-','source-cache-')) or path.suffix in {'.db', '.log', '.session', '.docx', '.pdf', '.gguf'}:
        errors.append(name + ': private/runtime artifact')
        continue
    try:
        text = path.read_text(encoding='utf-8')
    except (UnicodeError, OSError):
        continue
    if re.search(r'\b\d{8,12}:[A-Za-z0-9_-]{30,}\b|\bgh[pousr]_[A-Za-z0-9]{30,}\b', text):
        errors.append(name + ': potential credential')
if errors:
    raise SystemExit('\n'.join(errors))
print(f'Checked {len(paths)} publication files. No obvious private artifacts or tokens; not a full security audit.')
