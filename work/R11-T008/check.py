#!/usr/bin/env python3
"""Automated verification for R11-T008: git check-ignore integration test."""

import json
import os
import pathlib
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
AUTHOR_NAME = "Course Student"
AUTHOR_EMAIL = "student@example.invalid"

def run(args, cwd, env=None, check=True):
    return subprocess.run(
        args, cwd=cwd, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check
    )

def setup_fixture(repo):
    repo.mkdir()
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": AUTHOR_NAME,
        "GIT_AUTHOR_EMAIL": AUTHOR_EMAIL,
        "GIT_COMMITTER_NAME": AUTHOR_NAME,
        "GIT_COMMITTER_EMAIL": AUTHOR_EMAIL,
    })
    run(["git", "init", "-b", "main"], cwd=repo, env=env)
    run(["git", "config", "user.name", AUTHOR_NAME], cwd=repo, env=env)
    run(["git", "config", "user.email", AUTHOR_EMAIL], cwd=repo, env=env)
    
    (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
    run(["git", "add", ".gitignore"], cwd=repo, env=env)
    run(["git", "commit", "-m", "A: add gitignore"], cwd=repo, env=env)
    
    (repo / "debug.log").write_text("log content\n", encoding="utf-8")
    (repo / "tracked.txt").write_text("content\n", encoding="utf-8")
    
    return env

def main():
    inputs = {
        "command": "git check-ignore debug.log tracked.txt",
        "gitignore_pattern": "*.log"
    }
    expected = {
        "exit_code": 0,
        "ignored_matches": ["debug.log"],
        "non_ignored_excluded": ["tracked.txt"]
    }
    
    with tempfile.TemporaryDirectory(prefix="R11-T008-") as tmp:
        repo = pathlib.Path(tmp) / "repo"
        env = setup_fixture(repo)
        
        # Test 1: Check both files; should report debug.log and exit 0
        res = run(["git", "check-ignore", "debug.log", "tracked.txt"], cwd=repo, env=env)
        assert res.returncode == 0
        assert "debug.log" in res.stdout
        assert "tracked.txt" not in res.stdout
        
        # Test 2: Check non-ignored file only; must exit with code 1
        res_tracked = run(["git", "check-ignore", "tracked.txt"], cwd=repo, env=env, check=False)
        assert res_tracked.returncode == 1, "check-ignore on non-ignored file must exit 1"
        assert res_tracked.stdout.strip() == ""
        
        # Test 3: Verify read-only nature
        status = run(["git", "status", "--porcelain=v1"], cwd=repo, env=env).stdout.strip()
        assert "tracked.txt" in status
        assert "debug.log" not in status, "debug.log must be ignored by git status"
        
        actual = {
            "res_returncode": res.returncode,
            "res_stdout": res.stdout.strip(),
            "res_tracked_returncode": res_tracked.returncode,
            "assertions_passed": [
                "check-ignore exits 0 and prints ignored file debug.log",
                "check-ignore excludes tracked.txt from ignored matches",
                "check-ignore exits 1 when run exclusively on non-ignored files",
                "working tree and status confirm debug.log is ignored"
            ]
        }
        
    (HERE / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    (HERE / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    (HERE / "actual.json").write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    
    git_v = run(["git", "--version"], cwd=HERE).stdout.strip()
    py_v = run(["python3", "--version"], cwd=HERE).stdout.strip()
    (HERE / "versions.txt").write_text(f"{git_v}\n{py_v}\n", encoding="utf-8")
    print("PASS: R11-T008 git check-ignore integration test assertions verified")

if __name__ == "__main__":
    main()
