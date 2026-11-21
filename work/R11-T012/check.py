#!/usr/bin/env python3
"""
Automated verification script for task R11-T012:
'Don’t consider changes for tracked file.' (git update-index --assume-unchanged)

Verifies:
1. Setup scenario:
   - Init repo on 'main'
   - Author: 'Course Student <student@example.invalid>'
   - Commit A: notes.txt = "alpha\n"
   - Commit B: notes.txt appended with "beta\n"
   - Branch topic created at Commit B
   - Commit C on topic: todo.txt = "one\n"
2. Modifies notes.txt locally on disk.
3. Captures dynamic rev-parse, status, ls-files -v before and after assume-unchanged.
4. Asserts:
   - Refs (HEAD, main, topic) and commit ancestry (A->B->C) unchanged.
   - Index blob SHA unchanged with 'h' flag set in 'git ls-files -v'.
   - Working tree retains local edits while 'git status --porcelain' is empty.
5. Saves inputs, expected vs actual results, and git/python versions into results.json.
"""

import os
import sys
import json
import subprocess
import tempfile
import platform


def run_cmd(cmd: str, cwd: str) -> str:
    """Executes a command using subprocess with check=True and returns stripped stdout."""
    res = subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        check=True
    )
    return res.stdout.strip()


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results_path = os.path.join(script_dir, "results.json")

    git_ver = subprocess.run("git --version", shell=True, capture_output=True, text=True, check=True).stdout.strip()
    py_ver = sys.version.replace("\n", " ")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: Initialize branch main and set author configuration
        run_cmd("git init -b main", tmpdir)
        run_cmd("git config user.name \"Course Student\"", tmpdir)
        run_cmd("git config user.email \"student@example.invalid\"", tmpdir)

        # Step 2: Commit A (notes.txt = "alpha\n")
        notes_file = os.path.join(tmpdir, "notes.txt")
        with open(notes_file, "w", encoding="utf-8") as f:
            f.write("alpha\n")
        run_cmd("git add notes.txt", tmpdir)
        run_cmd("git commit -m \"Commit A\"", tmpdir)
        commit_a = run_cmd("git rev-parse HEAD", tmpdir)

        # Step 3: Commit B (append "beta\n")
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write("beta\n")
        run_cmd("git add notes.txt", tmpdir)
        run_cmd("git commit -m \"Commit B\"", tmpdir)
        commit_b = run_cmd("git rev-parse HEAD", tmpdir)

        # Step 4: Create branch topic at Commit B and switch to it
        run_cmd("git branch topic", tmpdir)
        run_cmd("git checkout topic", tmpdir)

        # Step 5: Commit C on topic (todo.txt = "one\n")
        todo_file = os.path.join(tmpdir, "todo.txt")
        with open(todo_file, "w", encoding="utf-8") as f:
            f.write("one\n")
        run_cmd("git add todo.txt", tmpdir)
        run_cmd("git commit -m \"Commit C\"", tmpdir)
        commit_c = run_cmd("git rev-parse HEAD", tmpdir)

        # Step 6: Modify notes.txt locally
        local_edit = "local modification\n"
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write(local_edit)

        # Capture Before State
        before_head = run_cmd("git rev-parse HEAD", tmpdir)
        before_main = run_cmd("git rev-parse main", tmpdir)
        before_topic = run_cmd("git rev-parse topic", tmpdir)
        before_ancestry = run_cmd("git rev-list --topo-order HEAD", tmpdir).splitlines()
        before_ls_files = run_cmd("git ls-files -v -s notes.txt", tmpdir)
        before_status = run_cmd("git status --porcelain", tmpdir)
        before_disk_content = open(notes_file, "r", encoding="utf-8").read()

        # Step 7: Run git update-index --assume-unchanged notes.txt
        run_cmd("git update-index --assume-unchanged notes.txt", tmpdir)

        # Capture After State
        after_head = run_cmd("git rev-parse HEAD", tmpdir)
        after_main = run_cmd("git rev-parse main", tmpdir)
        after_topic = run_cmd("git rev-parse topic", tmpdir)
        after_ancestry = run_cmd("git rev-list --topo-order HEAD", tmpdir).splitlines()
        after_ls_files = run_cmd("git ls-files -v -s notes.txt", tmpdir)
        after_status = run_cmd("git status --porcelain", tmpdir)
        after_diff = run_cmd("git diff", tmpdir)
        after_disk_content = open(notes_file, "r", encoding="utf-8").read()

        # Extract blob SHAs and flags
        before_flag = before_ls_files.split()[0]
        after_flag = after_ls_files.split()[0]
        before_blob_sha = before_ls_files.split()[2]
        after_blob_sha = after_ls_files.split()[2]

        # Assertions
        assert before_head == after_head == commit_c, f"HEAD ref changed: {before_head} -> {after_head}"
        assert before_main == after_main == commit_b, f"main ref changed: {before_main} -> {after_main}"
        assert before_topic == after_topic == commit_c, f"topic ref changed: {before_topic} -> {after_topic}"
        assert before_ancestry == after_ancestry == [commit_c, commit_b, commit_a], "Commit ancestry changed"

        assert before_flag == "H", f"Expected before flag 'H', got '{before_flag}'"
        assert after_flag == "h", f"Expected after flag 'h', got '{after_flag}'"
        assert before_blob_sha == after_blob_sha, f"Index blob SHA changed: {before_blob_sha} != {after_blob_sha}"

        assert after_disk_content == "alpha\nbeta\nlocal modification\n", "Working tree edits lost on disk"
        assert after_status == "", f"git status --porcelain is not empty: '{after_status}'"
        assert after_diff == "", f"git diff is not empty: '{after_diff}'"

        results_data = {
            "tool_versions": {
                "git": git_ver,
                "python": py_ver,
                "platform": platform.platform()
            },
            "inputs": {
                "author": "Course Student <student@example.invalid>",
                "initial_branch": "main",
                "commit_a": {"file": "notes.txt", "content": "alpha\n", "message": "Commit A"},
                "commit_b": {"file": "notes.txt", "content_appended": "beta\n", "message": "Commit B"},
                "branch_topic": {"fork_point": "Commit B"},
                "commit_c": {"branch": "topic", "file": "todo.txt", "content": "one\n", "message": "Commit C"},
                "local_edit": {"file": "notes.txt", "content_appended": "local modification\n"},
                "command": "git update-index --assume-unchanged notes.txt"
            },
            "expected_results": {
                "refs_and_ancestry": "HEAD, main, topic refs and A->B->C commit ancestry remain unchanged",
                "index_blob_sha": "Index blob SHA remains identical before and after",
                "index_flag": "Index flag changes from 'H' (tracked) to 'h' (assume-unchanged)",
                "working_tree": "Local edits retained on disk (alpha\\nbeta\\nlocal modification\\n)",
                "status_clean": "git status --porcelain is empty and git diff is empty"
            },
            "actual_results": {
                "commit_ids": {
                    "commit_a": commit_a,
                    "commit_b": commit_b,
                    "commit_c": commit_c
                },
                "before": {
                    "head": before_head,
                    "main": before_main,
                    "topic": before_topic,
                    "ancestry": before_ancestry,
                    "ls_files": before_ls_files,
                    "flag": before_flag,
                    "blob_sha": before_blob_sha,
                    "status_porcelain": before_status,
                    "disk_content": before_disk_content
                },
                "after": {
                    "head": after_head,
                    "main": after_main,
                    "topic": after_topic,
                    "ancestry": after_ancestry,
                    "ls_files": after_ls_files,
                    "flag": after_flag,
                    "blob_sha": after_blob_sha,
                    "status_porcelain": after_status,
                    "diff": after_diff,
                    "disk_content": after_disk_content
                },
                "assertions_passed": True
            }
        }

        os.makedirs(os.path.dirname(results_path), exist_ok=True)
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)

        print("Verification passed successfully.")
        print(f"Saved results to {results_path}")


if __name__ == "__main__":
    main()
