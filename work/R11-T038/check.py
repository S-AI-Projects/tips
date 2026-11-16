import json
import platform
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
test = root / "tests/guides/add_custom_editors.py"
evidence = Path(__file__).resolve().parent

normal = subprocess.run(
    [sys.executable, str(test)],
    capture_output=True,
    text=True
)

assert normal.returncode == 0, normal.stdout + normal.stderr

omitted = subprocess.run(
    [sys.executable, str(test), "--omit-decisive-command"],
    capture_output=True,
    text=True
)

assert omitted.returncode != 0, "Missing command was not detected"

versions = {
    "python": platform.python_version(),
    "git": subprocess.run(
        ["git", "--version"],
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()
}

(evidence / "inputs.json").write_text(json.dumps({
    "branch": "main",
    "author": "Course Student",
    "email": "student@example.invalid",
    "commits": ["A: alpha", "B: beta", "C: todo one"],
    "topic_branch": "commit B",
    "command": "git config --global core.editor '$EDITOR'"
}, indent=2) + "\n")

(evidence / "results.json").write_text(json.dumps({
    "normal_test": normal.stdout,
    "omitted_command_exit_code": omitted.returncode,
    "versions": versions
}, indent=2) + "\n")

print("PASS: Normal test")
print("PASS: Missing command correctly detected")
print("Evidence saved successfully")
