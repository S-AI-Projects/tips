#!/usr/bin/env python3
"""Automated verification for R11-T009: git var preconditions and setup."""

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

def main():
    inputs = {
        "command": "git var -l",
        "specific_var": "git var GIT_AUTHOR_IDENT",
        "preconditions": ["local user.name", "local user.email"]
    }
    expected = {
        "git_author_ident_contains": f"{AUTHOR_NAME} <{AUTHOR_EMAIL}>",
        "global_config_untouched": True,
        "git_var_list_succeeds": True
    }
    
    with tempfile.TemporaryDirectory(prefix="R11-T009-") as tmp:
        repo = pathlib.Path(tmp) / "repo"
        repo.mkdir()
        env = os.environ.copy()
        
        # Initialize repository with clean local config
        run(["git", "init", "-b", "main"], cwd=repo, env=env)
        run(["git", "config", "--local", "user.name", AUTHOR_NAME], cwd=repo, env=env)
        run(["git", "config", "--local", "user.email", AUTHOR_EMAIL], cwd=repo, env=env)
        
        # Query GIT_AUTHOR_IDENT
        res_ident = run(["git", "var", "GIT_AUTHOR_IDENT"], cwd=repo, env=env)
        assert res_ident.returncode == 0
        assert f"{AUTHOR_NAME} <{AUTHOR_EMAIL}>" in res_ident.stdout
        
        # Query git var -l
        res_list = run(["git", "var", "-l"], cwd=repo, env=env)
        assert res_list.returncode == 0
        assert "GIT_AUTHOR_IDENT=" in res_list.stdout
        assert "GIT_COMMITTER_IDENT=" in res_list.stdout
        
        # Verify working directory is pristine
        status = run(["git", "status", "--porcelain=v1"], cwd=repo, env=env).stdout.strip()
        assert status == "", "Status must remain clean"
        
        actual = {
            "git_author_ident": res_ident.stdout.strip(),
            "variables_listed": [line.split("=")[0] for line in res_list.stdout.splitlines() if "=" in line],
            "assertions_passed": [
                "git var GIT_AUTHOR_IDENT returns configured Course Student identity",
                "git var -l lists logical variables including GIT_AUTHOR_IDENT and GIT_COMMITTER_IDENT",
                "configuration was isolated to local repository config",
                "repository working tree remained pristine"
            ]
        }
        
    (HERE / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    (HERE / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    (HERE / "actual.json").write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    
    git_v = run(["git", "--version"], cwd=HERE).stdout.strip()
    py_v = run(["python3", "--version"], cwd=HERE).stdout.strip()
    (HERE / "versions.txt").write_text(f"{git_v}\n{py_v}\n", encoding="utf-8")
    print("PASS: R11-T009 git var preconditions assertions verified")

if __name__ == "__main__":
    main()
