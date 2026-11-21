#!/usr/bin/env python3
r"""
Automated verification script for task R11-T014:
'Stash specific files' (git stash push -m '<message>' -- <file>)

Verifies:
1. Setup scenario:
   - Bare remote repository ('remote.git') via file:// URL
   - Working repo initialized on 'main'
   - Author: 'Course Student <student@example.invalid>'
   - Commit A: notes.txt = "alpha\n"
   - Commit B: notes.txt appended with "beta\n"
   - Branch 'topic' created at Commit B
   - Commit C on 'main': todo.txt = "one\n"
   - Push 'main' to local 'origin' (origin/main at Commit C)
2. Checkout 'topic' (at Commit B).
3. Modify tracked notes.txt and create/modify extra.txt.
4. Run: git stash push -m 'wip notes' -- notes.txt
5. Assert at least 4 state facts using dynamic object IDs:
   (1) refs/stash exists and git rev-parse stash^1 equals topic (Commit B)
   (2) notes.txt in working tree matches Commit B ("alpha\nbeta\n"), while extra.txt remains modified/un-stashed in git status --porcelain
   (3) Branch refs topic (at B), main (at C), and remote ref origin/main (at C) stayed fixed
   (4) git stash list contains 'wip notes' referencing topic
6. Saves inputs, expected vs actual results, and git/python versions into work/R11-T014/results.json.
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
        # Step 1: Initialize local bare remote
        bare_remote_dir = os.path.join(tmpdir, "remote.git")
        run_cmd(f"git init --bare \"{bare_remote_dir}\"", tmpdir)

        # Step 2: Initialize working repository on branch main
        repo_dir = os.path.join(tmpdir, "repo")
        os.makedirs(repo_dir)

        run_cmd("git init -b main", repo_dir)
        run_cmd("git config user.name \"Course Student\"", repo_dir)
        run_cmd("git config user.email \"student@example.invalid\"", repo_dir)
        run_cmd(f"git remote add origin \"file://{bare_remote_dir}\"", repo_dir)

        # Step 3: Commit A (notes.txt = "alpha\n")
        notes_file = os.path.join(repo_dir, "notes.txt")
        with open(notes_file, "w", encoding="utf-8") as f:
            f.write("alpha\n")
        run_cmd("git add notes.txt", repo_dir)
        run_cmd("git commit -m \"Commit A\"", repo_dir)
        commit_a = run_cmd("git rev-parse HEAD", repo_dir)

        # Step 4: Commit B (append "beta\n")
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write("beta\n")
        run_cmd("git add notes.txt", repo_dir)
        run_cmd("git commit -m \"Commit B\"", repo_dir)
        commit_b = run_cmd("git rev-parse HEAD", repo_dir)

        # Step 5: Create branch topic at Commit B
        run_cmd("git branch topic", repo_dir)

        # Step 6: Commit C on main (todo.txt = "one\n")
        todo_file = os.path.join(repo_dir, "todo.txt")
        with open(todo_file, "w", encoding="utf-8") as f:
            f.write("one\n")
        run_cmd("git add todo.txt", repo_dir)
        run_cmd("git commit -m \"Commit C\"", repo_dir)
        commit_c = run_cmd("git rev-parse HEAD", repo_dir)

        # Step 7: Push main to local origin (origin/main at Commit C)
        run_cmd("git push -u origin main", repo_dir)
        origin_main_before = run_cmd("git rev-parse origin/main", repo_dir)
        assert origin_main_before == commit_c, "origin/main does not point to Commit C"

        # Step 8: Checkout topic (at Commit B)
        run_cmd("git checkout topic", repo_dir)
        topic_before = run_cmd("git rev-parse topic", repo_dir)
        main_before = run_cmd("git rev-parse main", repo_dir)
        assert topic_before == commit_b, "topic branch does not point to Commit B"

        # Step 9: Modify tracked notes.txt and create/modify extra.txt
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write("wip modifications\n")

        extra_file = os.path.join(repo_dir, "extra.txt")
        with open(extra_file, "w", encoding="utf-8") as f:
            f.write("extra un-stashed content\n")

        # Step 10: Run git stash push -m 'wip notes' -- notes.txt
        stash_output = run_cmd("git stash push -m 'wip notes' -- notes.txt", repo_dir)

        # Capture post-stash state
        stash_commit = run_cmd("git rev-parse refs/stash", repo_dir)
        stash_parent1 = run_cmd("git rev-parse stash^1", repo_dir)
        status_porcelain = run_cmd("git status --porcelain", repo_dir)
        notes_content_after = open(notes_file, "r", encoding="utf-8").read()
        extra_content_after = open(extra_file, "r", encoding="utf-8").read()
        topic_after = run_cmd("git rev-parse topic", repo_dir)
        main_after = run_cmd("git rev-parse main", repo_dir)
        origin_main_after = run_cmd("git rev-parse origin/main", repo_dir)
        stash_list = run_cmd("git stash list", repo_dir)

        # --- Assertions (at least 4 state facts) ---
        # Fact 1: refs/stash exists and git rev-parse stash^1 equals topic (commit B)
        assert stash_commit != "", "refs/stash was not created"
        assert stash_parent1 == commit_b, f"stash^1 {stash_parent1} != Commit B {commit_b}"
        assert stash_parent1 == topic_after, f"stash^1 {stash_parent1} != topic {topic_after}"

        # Fact 2: notes.txt in working tree matches commit B ("alpha\nbeta\n"), while extra.txt remains modified/un-stashed in git status --porcelain
        assert notes_content_after == "alpha\nbeta\n", f"notes.txt content '{notes_content_after}' != 'alpha\\nbeta\\n'"
        assert "notes.txt" not in status_porcelain, "notes.txt still appears in git status --porcelain"
        assert "extra.txt" in status_porcelain, "extra.txt missing from git status --porcelain"
        assert extra_content_after == "extra un-stashed content\n", "extra.txt content altered unexpectedly"

        # Fact 3: Branch refs topic (at B), main (at C), and remote ref origin/main (at C) stayed fixed
        assert topic_before == topic_after == commit_b, f"topic ref moved: {topic_before} -> {topic_after}"
        assert main_before == main_after == commit_c, f"main ref moved: {main_before} -> {main_after}"
        assert origin_main_before == origin_main_after == commit_c, f"origin/main ref moved: {origin_main_before} -> {origin_main_after}"

        # Fact 4: git stash list contains 'wip notes' referencing topic
        assert "wip notes" in stash_list, "'wip notes' message missing from git stash list"
        assert "topic" in stash_list, "'topic' branch name missing from git stash list entry"

        results_data = {
            "tool_versions": {
                "git": git_ver,
                "python": py_ver,
                "platform": platform.platform()
            },
            "inputs": {
                "bare_remote": f"file://{bare_remote_dir}",
                "author": "Course Student <student@example.invalid>",
                "initial_branch": "main",
                "commit_a": {"file": "notes.txt", "content": "alpha\n", "message": "Commit A"},
                "commit_b": {"file": "notes.txt", "content_appended": "beta\n", "message": "Commit B"},
                "branch_topic": {"fork_point": "Commit B"},
                "commit_c": {"branch": "main", "file": "todo.txt", "content": "one\n", "message": "Commit C"},
                "remote_push": {"branch": "main", "remote_ref": "origin/main"},
                "modifications_on_topic": {
                    "tracked_file": {"file": "notes.txt", "appended": "wip modifications\n"},
                    "untracked_extra_file": {"file": "extra.txt", "content": "extra un-stashed content\n"}
                },
                "stash_command": "git stash push -m 'wip notes' -- notes.txt"
            },
            "expected_results": {
                "fact_1": "refs/stash exists and git rev-parse stash^1 equals topic (Commit B)",
                "fact_2": "notes.txt in working tree matches Commit B ('alpha\\nbeta\\n'), while extra.txt remains modified/un-stashed in git status --porcelain",
                "fact_3": "Branch refs topic (at B), main (at C), and remote ref origin/main (at C) stayed fixed",
                "fact_4": "git stash list contains 'wip notes' referencing topic"
            },
            "actual_results": {
                "commit_ids": {
                    "commit_a": commit_a,
                    "commit_b": commit_b,
                    "commit_c": commit_c
                },
                "refs_before": {
                    "topic": topic_before,
                    "main": main_before,
                    "origin_main": origin_main_before
                },
                "stash_info": {
                    "stash_output": stash_output,
                    "stash_commit": stash_commit,
                    "stash_parent1": stash_parent1,
                    "stash_list": stash_list
                },
                "refs_after": {
                    "topic": topic_after,
                    "main": main_after,
                    "origin_main": origin_main_after
                },
                "working_tree_state": {
                    "notes_content": notes_content_after,
                    "extra_content": extra_content_after,
                    "status_porcelain": status_porcelain
                },
                "assertions_passed": True
            }
        }

        os.makedirs(os.path.dirname(results_path), exist_ok=True)
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)

        print("All 4 state facts verified successfully.")
        print(f"Saved results to {results_path}")


if __name__ == "__main__":
    main()
