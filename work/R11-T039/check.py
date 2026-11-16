import os
import json
import tempfile
import subprocess
import platform
from pathlib import Path

out = Path(__file__).resolve().parent

def git(args, cwd, env):
    return subprocess.run(
        ["git"] + args, cwd=cwd, env=env,
        check=True, capture_output=True, text=True
    ).stdout.strip()

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    repo = root / "repo"
    remote = root / "remote.git"
    home = root / "home"
    home.mkdir()

    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(home / ".gitconfig")
    })

    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    git(["config", "user.name", "Course Student"], repo, env)
    git(["config", "user.email", "student@example.invalid"], repo, env)

    (repo / "notes.txt").write_text("alpha\n")
    git(["add", "notes.txt"], repo, env)
    git(["commit", "-m", "A"], repo, env)

    (repo / "notes.txt").write_text("alpha\nbeta\n")
    git(["add", "notes.txt"], repo, env)
    git(["commit", "-m", "B"], repo, env)
    commit_b = git(["rev-parse", "HEAD"], repo, env)

    git(["branch", "topic"], repo, env)

    (repo / "todo.txt").write_text("one\n")
    git(["add", "todo.txt"], repo, env)
    git(["commit", "-m", "C"], repo, env)
    commit_c = git(["rev-parse", "HEAD"], repo, env)

    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    git(["remote", "add", "origin", remote.as_uri()], repo, env)
    git(["push", "origin", "topic"], repo, env)
    git(["fetch", "origin"], repo, env)
    git(["switch", "topic"], repo, env)

    assert git(["branch", "--show-current"], repo, env) == "topic"
    assert git(["diff", "--cached", "--name-only"], repo, env) == ""

    output = git(["branch", "-u", "origin/topic"], repo, env)

    actual = {
        "current_branch": git(["branch", "--show-current"], repo, env),
        "upstream": git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], repo, env),
        "remote": git(["config", "--local", "--get", "branch.topic.remote"], repo, env),
        "merge": git(["config", "--local", "--get", "branch.topic.merge"], repo, env),
        "topic_matches_origin": git(["rev-parse", "topic"], repo, env) == git(["rev-parse", "origin/topic"], repo, env),
        "main_at_C": git(["rev-parse", "main"], repo, env) == commit_c,
        "staged_empty": git(["diff", "--cached", "--name-only"], repo, env) == "",
        "working_tree_clean": git(["status", "--porcelain"], repo, env) == ""
    }

    checks = {
        "current branch is topic": actual["current_branch"] == "topic",
        "upstream is origin/topic": actual["upstream"] == "origin/topic",
        "remote is origin": actual["remote"] == "origin",
        "merge branch is refs/heads/topic": actual["merge"] == "refs/heads/topic",
        "topic matches origin/topic": actual["topic_matches_origin"],
        "main remains at commit C": actual["main_at_C"],
        "staged changes remain empty": actual["staged_empty"],
        "working tree remains clean": actual["working_tree_clean"]
    }

    (out / "inputs.json").write_text(json.dumps({
        "commit_B": commit_b,
        "commit_C": commit_c,
        "command": "git branch -u origin/topic",
        "remote": remote.as_uri()
    }, indent=2) + "\n")

    (out / "expected.json").write_text(json.dumps({
        "upstream": "origin/topic",
        "remote": "origin",
        "merge": "refs/heads/topic"
    }, indent=2) + "\n")

    (out / "results.json").write_text(json.dumps({
        "command_output": output,
        "actual": actual,
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks)
    }, indent=2) + "\n")

    (out / "versions.txt").write_text(
        git(["--version"], repo, env) + "\nPython " + platform.python_version() + "\n"
    )

    for name, passed in checks.items():
        print(("PASS" if passed else "FAIL") + ": " + name)

    assert all(checks.values())

print("PASS: All R11-T039 checks")
