#!/usr/bin/env python3
"""Automated verification for R11-T007: git diff HEAD failure diagnosis and fix."""

import json
import os
import pathlib
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
AUTHOR_NAME = "Course Student"
AUTHOR_EMAIL = "student@example.invalid"
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

def run(args, cwd, env=None, check=True):
    return subprocess.run(
        args, cwd=cwd, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check
    )

def main():
    inputs = {
        "command": "git diff HEAD",
        "violated_precondition": "Repository has no commits (unborn HEAD)",
        "correction": f"git diff {EMPTY_TREE_SHA}"
    }
    expected = {
        "bad_case_fails": True,
        "bad_case_exit_code": 128,
        "corrected_case_succeeds": True
    }
    
    with tempfile.TemporaryDirectory(prefix="R11-T007-") as tmp:
        repo = pathlib.Path(tmp) / "repo"
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
        
        # Add a file without committing
        (repo / "notes.txt").write_text("alpha\n", encoding="utf-8")
        run(["git", "add", "notes.txt"], cwd=repo, env=env)
        
        # 1. Violated precondition: git diff HEAD in unborn branch
        bad_res = run(["git", "diff", "HEAD"], cwd=repo, env=env, check=False)
        assert bad_res.returncode == 128, f"Expected 128 but got {bad_res.returncode}"
        assert "fatal: ambiguous argument 'HEAD'" in bad_res.stderr
        
        # 2. Correction: diff against empty tree SHA
        corr_res = run(["git", "diff", EMPTY_TREE_SHA], cwd=repo, env=env)
        assert corr_res.returncode == 0
        assert "notes.txt" in corr_res.stdout
        
        # 3. Normal case after commit
        run(["git", "commit", "-m", "A: add alpha"], cwd=repo, env=env)
        (repo / "notes.txt").write_text("alpha\nbeta\n", encoding="utf-8")
        normal_res = run(["git", "diff", "HEAD"], cwd=repo, env=env)
        assert normal_res.returncode == 0
        assert "+beta" in normal_res.stdout
        
        actual = {
            "bad_command_exit_code": bad_res.returncode,
            "bad_command_stderr": bad_res.stderr.strip(),
            "corrected_command_exit_code": corr_res.returncode,
            "corrected_command_output": corr_res.stdout.strip(),
            "assertions_passed": [
                "git diff HEAD fails with exit code 128 on unborn HEAD",
                "fatal diagnostic confirms unknown revision 'HEAD'",
                "diff against empty tree hash 4b825dc... succeeds with exit code 0",
                "after initial commit, git diff HEAD succeeds and displays staged/unstaged changes"
            ]
        }
        
    (HERE / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    (HERE / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    (HERE / "actual.json").write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    
    git_v = run(["git", "--version"], cwd=HERE).stdout.strip()
    py_v = run(["python3", "--version"], cwd=HERE).stdout.strip()
    (HERE / "versions.txt").write_text(f"{git_v}\n{py_v}\n", encoding="utf-8")
    print("PASS: R11-T007 failure diagnosis and fix assertions verified")

if __name__ == "__main__":
    main()
