#!/usr/bin/env python3
"""Automated verification for R11-T003: recovery from accidental reset before pruning."""

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
    
    (repo / "notes.txt").write_text("alpha\n", encoding="utf-8")
    run(["git", "add", "notes.txt"], cwd=repo, env=env)
    run(["git", "commit", "-m", "A: add alpha"], cwd=repo, env=env)
    commit_a = run(["git", "rev-parse", "HEAD"], cwd=repo, env=env).stdout.strip()
    
    run(["git", "switch", "-c", "topic"], cwd=repo, env=env)
    with (repo / "notes.txt").open("a", encoding="utf-8") as f:
        f.write("beta\n")
    run(["git", "add", "notes.txt"], cwd=repo, env=env)
    run(["git", "commit", "-m", "B: add beta"], cwd=repo, env=env)
    commit_b = run(["git", "rev-parse", "HEAD"], cwd=repo, env=env).stdout.strip()
    
    run(["git", "switch", "main"], cwd=repo, env=env)
    (repo / "todo.txt").write_text("one\n", encoding="utf-8")
    run(["git", "add", "todo.txt"], cwd=repo, env=env)
    run(["git", "commit", "-m", "C: add todo"], cwd=repo, env=env)
    commit_c = run(["git", "rev-parse", "HEAD"], cwd=repo, env=env).stdout.strip()
    tree_c = run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, env=env).stdout.strip()
    
    return env, {"A": commit_a, "B": commit_b, "C": commit_c}, tree_c

def main():
    inputs = {
        "command": "git gc --prune=now --aggressive",
        "mistake": "git reset --hard HEAD~1",
        "recovery_mechanism": "git reset --hard HEAD@{1}"
    }
    expected = {
        "recovered_tree_matches_original": True,
        "todo_txt_restored": "one\n",
        "recovery_via_reflog_succeeds": True
    }
    
    with tempfile.TemporaryDirectory(prefix="R11-T003-") as tmp:
        repo = pathlib.Path(tmp) / "repo"
        env, commits, original_tree = setup_fixture(repo)
        
        # 1. Accidental reset
        run(["git", "reset", "--hard", "HEAD~1"], cwd=repo, env=env)
        assert run(["git", "rev-parse", "HEAD"], cwd=repo, env=env).stdout.strip() == commits["A"]
        
        # 2. Prune operation with intact reflog
        run(["git", "gc", "--prune=now", "--aggressive"], cwd=repo, env=env)
        
        # 3. Recover commit C via reflog
        reflog_target = run(["git", "rev-parse", "HEAD@{1}"], cwd=repo, env=env).stdout.strip()
        assert reflog_target == commits["C"], "Reflog must preserve commit C"
        
        run(["git", "reset", "--hard", "HEAD@{1}"], cwd=repo, env=env)
        recovered_tree = run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, env=env).stdout.strip()
        
        assert recovered_tree == original_tree, "Recovered tree hash must match original tree hash"
        assert (repo / "todo.txt").read_text(encoding="utf-8") == "one\n"
        assert run(["git", "status", "--porcelain=v1"], cwd=repo, env=env).stdout.strip() == ""
        
        actual = {
            "original_tree": original_tree,
            "recovered_tree": recovered_tree,
            "commit_recovered": commits["C"],
            "assertions_passed": [
                "accidental reset moved HEAD to commit A",
                "git gc --prune=now preserved commit C due to active reflog",
                "git reset --hard HEAD@{1} recovered original commit C",
                "recovered tree hash and file contents match expected exactly"
            ]
        }
        
    (HERE / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    (HERE / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    (HERE / "actual.json").write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    
    git_v = run(["git", "--version"], cwd=HERE).stdout.strip()
    py_v = run(["python3", "--version"], cwd=HERE).stdout.strip()
    (HERE / "versions.txt").write_text(f"{git_v}\n{py_v}\n", encoding="utf-8")
    print("PASS: R11-T003 recovery exercise assertions verified")

if __name__ == "__main__":
    main()
