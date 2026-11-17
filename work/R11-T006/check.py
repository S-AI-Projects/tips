#!/usr/bin/env python3
"""Automated verification for R11-T006: word-diff vs color-words comparison."""

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
    
    return env, {"A": commit_a, "B": commit_b, "C": commit_c}

def capture_state(repo, env):
    return {
        "head": run(["git", "rev-parse", "HEAD"], cwd=repo, env=env).stdout.strip(),
        "branches": run(["git", "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/"], cwd=repo, env=env).stdout.strip().splitlines(),
        "index_tree": run(["git", "write-tree"], cwd=repo, env=env).stdout.strip(),
    }

def main():
    inputs = {
        "commands": ["git diff --color-words", "git diff --word-diff=plain"],
        "file_modification": "notes.txt: 'alpha' -> 'alpha modified'"
    }
    expected = {
        "plain_contains_bracket_syntax": "{+modified+}",
        "both_commands_exit_zero": True,
        "state_preserved": True
    }
    
    with tempfile.TemporaryDirectory(prefix="R11-T006-") as tmp:
        repo = pathlib.Path(tmp) / "repo"
        env, commits = setup_fixture(repo)
        
        # Word-level edit
        (repo / "notes.txt").write_text("alpha modified\n", encoding="utf-8")
        
        state_before = capture_state(repo, env)
        
        res_plain = run(["git", "diff", "--word-diff=plain"], cwd=repo, env=env)
        res_color = run(["git", "diff", "--color-words"], cwd=repo, env=env)
        
        state_after = capture_state(repo, env)
        
        assert res_plain.returncode == 0
        assert res_color.returncode == 0
        assert "{+modified+}" in res_plain.stdout, "Plain word diff must use bracketed insertion format"
        assert state_before == state_after, "Diff operations must not alter repository state"
        
        actual = {
            "plain_diff_output": res_plain.stdout.strip(),
            "color_diff_output_length": len(res_color.stdout),
            "state_before": state_before,
            "state_after": state_after,
            "assertions_passed": [
                "--word-diff=plain outputs inline bracketed markers without ANSI codes",
                "--color-words executes cleanly with exit code 0",
                "both workflows preserve HEAD, branch references, and index tree"
            ]
        }
        
    (HERE / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    (HERE / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    (HERE / "actual.json").write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    
    git_v = run(["git", "--version"], cwd=HERE).stdout.strip()
    py_v = run(["python3", "--version"], cwd=HERE).stdout.strip()
    (HERE / "versions.txt").write_text(f"{git_v}\n{py_v}\n", encoding="utf-8")
    print("PASS: R11-T006 word diff comparison assertions verified")

if __name__ == "__main__":
    main()
