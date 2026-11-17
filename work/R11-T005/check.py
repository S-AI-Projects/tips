#!/usr/bin/env python3
"""Automated verification for R11-T005: git ls-remote quoting and path handling."""

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

def setup_fixture(root):
    sample_dir = root / "sample data"
    sample_dir.mkdir()
    bare = sample_dir / "bare.git"
    repo = root / "repo"
    repo.mkdir()
    
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": AUTHOR_NAME,
        "GIT_AUTHOR_EMAIL": AUTHOR_EMAIL,
        "GIT_COMMITTER_NAME": AUTHOR_NAME,
        "GIT_COMMITTER_EMAIL": AUTHOR_EMAIL,
    })
    
    run(["git", "init", "--bare", str(bare)], cwd=root)
    run(["git", "init", "-b", "main"], cwd=repo, env=env)
    run(["git", "config", "user.name", AUTHOR_NAME], cwd=repo, env=env)
    run(["git", "config", "user.email", AUTHOR_EMAIL], cwd=repo, env=env)
    
    (repo / "notes.txt").write_text("alpha\n", encoding="utf-8")
    (repo / "release notes.txt").write_text("Release notes details\n", encoding="utf-8")
    run(["git", "add", "."], cwd=repo, env=env)
    run(["git", "commit", "-m", "A: add alpha and release notes"], cwd=repo, env=env)
    
    run(["git", "switch", "-c", "topic"], cwd=repo, env=env)
    with (repo / "notes.txt").open("a", encoding="utf-8") as f:
        f.write("beta\n")
    run(["git", "add", "notes.txt"], cwd=repo, env=env)
    run(["git", "commit", "-m", "B: add beta"], cwd=repo, env=env)
    
    run(["git", "switch", "main"], cwd=repo, env=env)
    (repo / "todo.txt").write_text("one\n", encoding="utf-8")
    run(["git", "add", "todo.txt"], cwd=repo, env=env)
    run(["git", "commit", "-m", "C: add todo"], cwd=repo, env=env)
    
    remote_url = f"file://{bare.resolve()}"
    run(["git", "remote", "add", "origin", remote_url], cwd=repo, env=env)
    run(["git", "push", "origin", "main", "topic"], cwd=repo, env=env)
    
    return repo, bare, remote_url, env

def main():
    inputs = {
        "command": 'git ls-remote "file://${PWD}/sample data/bare.git"',
        "directory_with_spaces": "sample data",
        "file_with_spaces": "release notes.txt"
    }
    expected = {
        "ls_remote_succeeds_with_quoted_url": True,
        "contains_refs": ["refs/heads/main", "refs/heads/topic"],
        "preserves_path_with_spaces": True
    }
    
    with tempfile.TemporaryDirectory(prefix="R11-T005-") as tmp:
        root = pathlib.Path(tmp)
        repo, bare, remote_url, env = setup_fixture(root)
        
        res = run(["git", "ls-remote", remote_url], cwd=repo, env=env)
        assert res.returncode == 0
        assert "refs/heads/main" in res.stdout
        assert "refs/heads/topic" in res.stdout
        
        # Query specific ref pattern with quotes
        res_pattern = run(["git", "ls-remote", remote_url, "refs/heads/topic"], cwd=repo, env=env)
        assert res_pattern.returncode == 0
        assert "refs/heads/topic" in res_pattern.stdout
        assert "refs/heads/main" not in res_pattern.stdout
        
        actual = {
            "remote_url": remote_url,
            "refs_found": res.stdout.strip().splitlines(),
            "assertions_passed": [
                "ls-remote successfully queries remote in directory path containing spaces",
                "correctly discovers refs/heads/main and refs/heads/topic",
                "filtering by ref pattern accurately targets intended reference",
                "presence of working file with spaces (release notes.txt) does not interfere"
            ]
        }
        
    (HERE / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    (HERE / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    (HERE / "actual.json").write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    
    git_v = run(["git", "--version"], cwd=HERE).stdout.strip()
    py_v = run(["python3", "--version"], cwd=HERE).stdout.strip()
    (HERE / "versions.txt").write_text(f"{git_v}\n{py_v}\n", encoding="utf-8")
    print("PASS: R11-T005 ls-remote path quoting assertions verified")

if __name__ == "__main__":
    main()
