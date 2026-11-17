#!/usr/bin/env python3
"""Automated verification for R11-T002: git archive state transition."""

import json
import os
import pathlib
import subprocess
import tempfile
import zipfile

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
        "head_ref": run(["git", "symbolic-ref", "HEAD"], cwd=repo, env=env).stdout.strip(),
        "branches": run(["git", "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/"], cwd=repo, env=env).stdout.strip().splitlines(),
        "index_tree": run(["git", "write-tree"], cwd=repo, env=env).stdout.strip(),
        "staged": run(["git", "diff", "--cached", "--name-only"], cwd=repo, env=env).stdout.strip(),
        "status": run(["git", "status", "--porcelain=v1"], cwd=repo, env=env).stdout.strip(),
    }

def main():
    inputs = {
        "command": "git archive main --format=zip --output=main.zip",
        "author": {"name": AUTHOR_NAME, "email": AUTHOR_EMAIL},
        "target_ref": "main"
    }
    expected = {
        "archive_created": True,
        "archive_entries": ["notes.txt", "todo.txt"],
        "head_and_branches_unchanged": True,
        "index_tree_unchanged": True
    }
    
    with tempfile.TemporaryDirectory(prefix="R11-T002-") as tmp:
        repo = pathlib.Path(tmp) / "repo"
        env, commits = setup_fixture(repo)
        
        state_before = capture_state(repo, env)
        res = run(["git", "archive", "main", "--format=zip", "--output=main.zip"], cwd=repo, env=env)
        state_after = capture_state(repo, env)
        
        assert res.returncode == 0
        zip_path = repo / "main.zip"
        assert zip_path.exists(), "Archive file must be created"
        
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            assert "notes.txt" in namelist
            assert "todo.txt" in namelist
            assert ".git" not in namelist
            assert zf.read("notes.txt").decode("utf-8") == "alpha\n"
            assert zf.read("todo.txt").decode("utf-8") == "one\n"
        
        assert state_before["head"] == state_after["head"], "HEAD must not change"
        assert state_before["branches"] == state_after["branches"], "Branch refs must not change"
        assert state_before["index_tree"] == state_after["index_tree"], "Index tree must not change"
        assert state_before["staged"] == state_after["staged"], "Staging area must not change"
        
        actual = {
            "archive_path": str(zip_path),
            "archive_namelist": namelist,
            "state_before": state_before,
            "state_after": state_after,
            "assertions_passed": [
                "archive created successfully with format zip",
                "archive unzips to match commit C file contents exactly",
                "HEAD, branch refs, ancestry, and index tree remain identical before and after"
            ]
        }
        
    (HERE / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    (HERE / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    (HERE / "actual.json").write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    
    git_v = run(["git", "--version"], cwd=HERE).stdout.strip()
    py_v = run(["python3", "--version"], cwd=HERE).stdout.strip()
    (HERE / "versions.txt").write_text(f"{git_v}\n{py_v}\n", encoding="utf-8")
    print("PASS: R11-T002 git archive state transition assertions verified")

if __name__ == "__main__":
    main()
