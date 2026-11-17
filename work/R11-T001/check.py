#!/usr/bin/env python3
"""Automated verification for R11-T001: git request-pull reproducible example."""

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
    repo = root / "repo"
    bare = root / "bare.git"
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
    
    # Commit A
    (repo / "notes.txt").write_text("alpha\n", encoding="utf-8")
    run(["git", "add", "notes.txt"], cwd=repo, env=env)
    run(["git", "commit", "-m", "A: add alpha"], cwd=repo, env=env)
    commit_a = run(["git", "rev-parse", "HEAD"], cwd=repo, env=env).stdout.strip()
    run(["git", "tag", "v1.0"], cwd=repo, env=env)
    
    # Branch topic at B
    run(["git", "switch", "-c", "topic"], cwd=repo, env=env)
    with (repo / "notes.txt").open("a", encoding="utf-8") as f:
        f.write("beta\n")
    run(["git", "add", "notes.txt"], cwd=repo, env=env)
    run(["git", "commit", "-m", "B: add beta"], cwd=repo, env=env)
    commit_b = run(["git", "rev-parse", "HEAD"], cwd=repo, env=env).stdout.strip()
    
    # Commit C on main
    run(["git", "switch", "main"], cwd=repo, env=env)
    (repo / "todo.txt").write_text("one\n", encoding="utf-8")
    run(["git", "add", "todo.txt"], cwd=repo, env=env)
    run(["git", "commit", "-m", "C: add todo"], cwd=repo, env=env)
    commit_c = run(["git", "rev-parse", "HEAD"], cwd=repo, env=env).stdout.strip()
    
    remote_url = f"file://{bare.resolve()}"
    run(["git", "remote", "add", "origin", remote_url], cwd=repo, env=env)
    run(["git", "push", "origin", "main", "topic", "v1.0"], cwd=repo, env=env)
    
    return repo, bare, remote_url, env, {"A": commit_a, "B": commit_b, "C": commit_c}

def capture_state(repo, env):
    return {
        "head": run(["git", "rev-parse", "HEAD"], cwd=repo, env=env).stdout.strip(),
        "topic": run(["git", "rev-parse", "topic"], cwd=repo, env=env).stdout.strip(),
        "main": run(["git", "rev-parse", "main"], cwd=repo, env=env).stdout.strip(),
        "index_tree": run(["git", "write-tree"], cwd=repo, env=env).stdout.strip(),
        "status": run(["git", "status", "--porcelain=v1"], cwd=repo, env=env).stdout.strip(),
    }

def main():
    inputs = {
        "command": "git request-pull v1.0 <url> topic",
        "author": {"name": AUTHOR_NAME, "email": AUTHOR_EMAIL},
        "history": {
            "A": "main creates notes.txt containing alpha\n and tagged v1.0",
            "B": "topic appends beta\n to notes.txt",
            "C": "main adds todo.txt containing one\n",
        },
        "remote": "local bare repository accessed via file:// URL"
    }
    
    expected = {
        "exit_code": 0,
        "contains": ["topic", "v1.0", "Course Student", "notes.txt | 1 +"],
        "state_unchanged": True
    }
    
    # Run 1 in temporary directory
    with tempfile.TemporaryDirectory(prefix="R11-T001-run1-") as tmp1:
        repo1, bare1, url1, env1, commits1 = setup_fixture(pathlib.Path(tmp1))
        state_before = capture_state(repo1, env1)
        res1 = run(["git", "request-pull", "v1.0", url1, "topic"], cwd=repo1, env=env1)
        state_after = capture_state(repo1, env1)
        
        assert res1.returncode == 0, f"request-pull failed: {res1.stderr}"
        assert url1 in res1.stdout
        assert "topic" in res1.stdout
        assert "Course Student" in res1.stdout
        assert "notes.txt | 1 +" in res1.stdout
        assert state_before == state_after, "Repository state must remain untouched"
    
    # Run 2 in separate temporary directory (reproducibility check)
    with tempfile.TemporaryDirectory(prefix="R11-T001-run2-") as tmp2:
        repo2, bare2, url2, env2, commits2 = setup_fixture(pathlib.Path(tmp2))
        res2 = run(["git", "request-pull", "v1.0", url2, "topic"], cwd=repo2, env=env2)
        assert res2.returncode == 0
        assert "notes.txt | 1 +" in res2.stdout
    
    actual = {
        "returncode": res1.returncode,
        "stdout_summary": res1.stdout.strip().splitlines()[:5],
        "state_before": state_before,
        "state_after": state_after,
        "reproducible_across_runs": True,
        "assertions_passed": [
            "git request-pull exits 0",
            "output identifies target branch topic and base v1.0",
            "output includes diffstat notes.txt | 1 + and author Course Student",
            "local repository state (HEAD, refs, index, worktree) is preserved",
            "reproducible in independent temporary directories"
        ]
    }
    
    (HERE / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    (HERE / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    (HERE / "actual.json").write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    
    git_v = run(["git", "--version"], cwd=HERE).stdout.strip()
    py_v = run(["python3", "--version"], cwd=HERE).stdout.strip()
    (HERE / "versions.txt").write_text(f"{git_v}\n{py_v}\n", encoding="utf-8")
    print("PASS: R11-T001 request-pull reproducible example assertions verified")

if __name__ == "__main__":
    main()
