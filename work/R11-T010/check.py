#!/usr/bin/env python3
"""Automated verification for R11-T010: git config --global --unset exercise."""

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
        "status": run(["git", "status", "--porcelain=v1"], cwd=repo, env=env).stdout.strip(),
    }

def main():
    inputs = {
        "command": "git config --global --unset custom.setting",
        "mock_global_config": True
    }
    expected = {
        "entry_removed": True,
        "config_get_exits_1": True,
        "git_state_untouched": True
    }
    
    with tempfile.TemporaryDirectory(prefix="R11-T010-") as tmp:
        root = pathlib.Path(tmp)
        repo = root / "repo"
        mock_global = root / "global_gitconfig"
        mock_global.write_text("[custom]\n\tsetting = testval\n", encoding="utf-8")
        
        env, commits = setup_fixture(repo)
        env["GIT_CONFIG_GLOBAL"] = str(mock_global)
        
        # Verify initial value present
        res_before = run(["git", "config", "--global", "--get", "custom.setting"], cwd=repo, env=env)
        assert res_before.stdout.strip() == "testval"
        
        state_before = capture_state(repo, env)
        
        # Execute unset
        run(["git", "config", "--global", "--unset", "custom.setting"], cwd=repo, env=env)
        
        state_after = capture_state(repo, env)
        
        # Verify unset
        res_after = run(["git", "config", "--global", "--get", "custom.setting"], cwd=repo, env=env, check=False)
        assert res_after.returncode == 1, "Query after unset must exit 1"
        assert state_before == state_after, "Repository state must remain bit-for-bit identical"
        
        actual = {
            "query_after_returncode": res_after.returncode,
            "state_before": state_before,
            "state_after": state_after,
            "assertions_passed": [
                "custom.setting is successfully removed from global config",
                "git config --global --get returns exit code 1",
                "HEAD, branch refs, index tree, and working tree files remain pristine"
            ]
        }
        
    (HERE / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    (HERE / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    (HERE / "actual.json").write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    
    git_v = run(["git", "--version"], cwd=HERE).stdout.strip()
    py_v = run(["python3", "--version"], cwd=HERE).stdout.strip()
    (HERE / "versions.txt").write_text(f"{git_v}\n{py_v}\n", encoding="utf-8")
    print("PASS: R11-T010 git config --unset prediction exercise assertions verified")

if __name__ == "__main__":
    main()
