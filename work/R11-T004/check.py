#!/usr/bin/env python3
"""Automated verification for R11-T004: shallow clone branch and remote semantics."""

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

def setup_remote(root):
    bare = root / "bare.git"
    seed = root / "seed"
    seed.mkdir()
    
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": AUTHOR_NAME,
        "GIT_AUTHOR_EMAIL": AUTHOR_EMAIL,
        "GIT_COMMITTER_NAME": AUTHOR_NAME,
        "GIT_COMMITTER_EMAIL": AUTHOR_EMAIL,
    })
    
    run(["git", "init", "--bare", str(bare)], cwd=root)
    run(["git", "init", "-b", "main"], cwd=seed, env=env)
    run(["git", "config", "user.name", AUTHOR_NAME], cwd=seed, env=env)
    run(["git", "config", "user.email", AUTHOR_EMAIL], cwd=seed, env=env)
    
    (seed / "notes.txt").write_text("alpha\n", encoding="utf-8")
    run(["git", "add", "notes.txt"], cwd=seed, env=env)
    run(["git", "commit", "-m", "A: add alpha"], cwd=seed, env=env)
    
    run(["git", "switch", "-c", "topic"], cwd=seed, env=env)
    with (seed / "notes.txt").open("a", encoding="utf-8") as f:
        f.write("beta\n")
    run(["git", "add", "notes.txt"], cwd=seed, env=env)
    run(["git", "commit", "-m", "B: add beta"], cwd=seed, env=env)
    
    run(["git", "switch", "main"], cwd=seed, env=env)
    (seed / "todo.txt").write_text("one\n", encoding="utf-8")
    run(["git", "add", "todo.txt"], cwd=seed, env=env)
    run(["git", "commit", "-m", "C: add todo"], cwd=seed, env=env)
    
    remote_url = f"file://{bare.resolve()}"
    run(["git", "remote", "add", "origin", remote_url], cwd=seed, env=env)
    run(["git", "push", "origin", "main", "topic"], cwd=seed, env=env)
    run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=bare, env=env)
    
    return bare, remote_url, env

def main():
    inputs = {
        "command": "git clone <url> --depth 1",
        "remote_default_branch": "main",
        "remote_other_branch": "topic"
    }
    expected = {
        "default_clone_has_only_main": True,
        "default_clone_depth": 1,
        "topic_branch_not_fetched_by_default": True
    }
    
    with tempfile.TemporaryDirectory(prefix="R11-T004-") as tmp:
        root = pathlib.Path(tmp)
        bare, remote_url, env = setup_remote(root)
        
        # Clone 1: default shallow clone
        clone1 = root / "clone1"
        res1 = run(["git", "clone", "--depth", "1", remote_url, str(clone1)], cwd=root, env=env)
        assert res1.returncode == 0
        
        c1_branches = run(["git", "branch", "-a"], cwd=clone1, env=env).stdout.strip()
        c1_depth = run(["git", "rev-list", "--count", "HEAD"], cwd=clone1, env=env).stdout.strip()
        
        assert "main" in c1_branches, "main branch must be cloned"
        assert "topic" not in c1_branches, "unrelated branch topic must not be fetched in shallow clone"
        assert c1_depth == "1", "commit depth must be exactly 1"
        
        # Clone 2: explicit topic shallow clone
        clone2 = root / "clone2"
        res2 = run(["git", "clone", "--depth", "1", "--branch", "topic", remote_url, str(clone2)], cwd=root, env=env)
        assert res2.returncode == 0
        
        c2_branches = run(["git", "branch", "-a"], cwd=clone2, env=env).stdout.strip()
        c2_depth = run(["git", "rev-list", "--count", "HEAD"], cwd=clone2, env=env).stdout.strip()
        
        assert "topic" in c2_branches, "topic branch must be cloned"
        assert "main" not in c2_branches, "main branch must not be fetched when topic is specified"
        assert c2_depth == "1", "commit depth must be exactly 1"
        
        actual = {
            "clone1_branches": c1_branches.splitlines(),
            "clone1_depth": int(c1_depth),
            "clone2_branches": c2_branches.splitlines(),
            "clone2_depth": int(c2_depth),
            "assertions_passed": [
                "shallow clone without branch flag clones only remote default branch (main)",
                "shallow clone commit history depth is limited to 1",
                "unrelated branch (topic) is not fetched into local refs or remote-tracking refs",
                "explicit --branch topic clone fetches only the topic ref"
            ]
        }
        
    (HERE / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    (HERE / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    (HERE / "actual.json").write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    
    git_v = run(["git", "--version"], cwd=HERE).stdout.strip()
    py_v = run(["python3", "--version"], cwd=HERE).stdout.strip()
    (HERE / "versions.txt").write_text(f"{git_v}\n{py_v}\n", encoding="utf-8")
    print("PASS: R11-T004 shallow clone branch semantics assertions verified")

if __name__ == "__main__":
    main()
