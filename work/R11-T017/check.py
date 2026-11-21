#!/usr/bin/env python3
r"""
Automated verification script for task R11-T017:
'Apply last stashed state and delete it from stashed list' (git stash pop troubleshooting)

Verifies:
1. Setup scenario:
   - Init repo on 'main'
   - Author: 'Course Student <student@example.invalid>'
   - Commit A: notes.txt = "alpha\n"
   - Commit B: notes.txt appended with "beta\n"
   - Branch 'topic' created at Commit B
   - Commit C on 'main': todo.txt = "one\n"
2. Create stash@{0} modifying notes.txt ("alpha\nbeta\nstashed-line\n").
3. Introduce uncommitted conflicting local edit to notes.txt in working tree ("alpha\nbeta\nuncommitted-conflict\n").
4. Bad case:
   - Run 'git stash pop'
   - Assert returncode != 0
   - Assert stderr indicates overwrite/merge conflict category
   - Assert stash@{0} is still preserved on stash stack
5. Smallest correction:
   - Clear/isolate conflicting working-tree modification (git checkout -- notes.txt / git stash push)
   - Re-run git stash pop
   - Assert returncode == 0
   - Assert notes.txt contains "stashed-line"
   - Assert stash@{0} is dropped
   - Assert main (Commit C) and topic (Commit B) refs remain unchanged
6. Saves inputs, expected vs actual results, and git/python versions into work/R11-T017/results.json.
"""

import os
import sys
import json
import subprocess
import tempfile
import platform


def run_cmd(cmd: str, cwd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Executes a command using subprocess and returns CompletedProcess."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        check=check
    )


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results_path = os.path.join(script_dir, "results.json")

    git_ver = run_cmd("git --version", ".").stdout.strip()
    py_ver = sys.version.replace("\n", " ")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: Initialize repository on branch main
        run_cmd("git init -b main", tmpdir)
        run_cmd("git config user.name \"Course Student\"", tmpdir)
        run_cmd("git config user.email \"student@example.invalid\"", tmpdir)

        # Commit A (notes.txt = "alpha\n")
        notes_file = os.path.join(tmpdir, "notes.txt")
        with open(notes_file, "w", encoding="utf-8") as f:
            f.write("alpha\n")
        run_cmd("git add notes.txt", tmpdir)
        run_cmd("git commit -m \"Commit A\"", tmpdir)
        commit_a = run_cmd("git rev-parse HEAD", tmpdir).stdout.strip()

        # Commit B (notes.txt appended with "beta\n")
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write("beta\n")
        run_cmd("git add notes.txt", tmpdir)
        run_cmd("git commit -m \"Commit B\"", tmpdir)
        commit_b = run_cmd("git rev-parse HEAD", tmpdir).stdout.strip()

        # Branch topic at Commit B
        run_cmd("git branch topic", tmpdir)

        # Commit C on main (todo.txt = "one\n")
        todo_file = os.path.join(tmpdir, "todo.txt")
        with open(todo_file, "w", encoding="utf-8") as f:
            f.write("one\n")
        run_cmd("git add todo.txt", tmpdir)
        run_cmd("git commit -m \"Commit C\"", tmpdir)
        commit_c = run_cmd("git rev-parse HEAD", tmpdir).stdout.strip()

        # Fact 1: Initial branch refs
        topic_sha = run_cmd("git rev-parse topic", tmpdir).stdout.strip()
        main_sha = run_cmd("git rev-parse main", tmpdir).stdout.strip()
        assert main_sha == commit_c, f"main ref {main_sha} != Commit C {commit_c}"
        assert topic_sha == commit_b, f"topic ref {topic_sha} != Commit B {commit_b}"

        # Step 2: Create stash@{0} modifying notes.txt
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write("stashed-line\n")
        run_cmd("git stash push -m \"stash-edit\" -- notes.txt", tmpdir)
        stash_sha = run_cmd("git rev-parse stash@{0}", tmpdir).stdout.strip()

        # Step 3: Introduce uncommitted conflicting edit to notes.txt in working tree
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write("uncommitted-conflict\n")

        # Step 4: Bad case - run git stash pop
        bad_pop_res = run_cmd("git stash pop", tmpdir, check=False)
        bad_pop_exit = bad_pop_res.returncode
        bad_pop_stderr = bad_pop_res.stderr.strip()
        bad_pop_stdout = bad_pop_res.stdout.strip()

        # Check if stash@{0} is still present
        stash_after_fail = run_cmd("git rev-parse stash@{0}", tmpdir, check=False)
        stash_still_present = (stash_after_fail.returncode == 0)

        # Fact 2: Bad case failure
        assert bad_pop_exit != 0, "git stash pop unexpectedly succeeded on dirty conflicting file"
        assert "notes.txt" in bad_pop_stderr, f"'notes.txt' missing from stderr:\n{bad_pop_stderr}"
        assert ("overwritten" in bad_pop_stderr or "conflict" in bad_pop_stderr or "overwritten" in bad_pop_stdout or "conflict" in bad_pop_stdout), \
            f"Expected overwrite or conflict error indication in output:\n{bad_pop_stderr}\n{bad_pop_stdout}"
        assert stash_still_present is True, "stash@{0} was unexpectedly dropped after failed pop"

        # Step 5: Smallest correction - discard disposable conflicting working-tree modification
        run_cmd("git checkout -- notes.txt", tmpdir)

        # Re-run git stash pop
        good_pop_res = run_cmd("git stash pop", tmpdir, check=True)
        good_pop_exit = good_pop_res.returncode

        notes_content_after = open(notes_file, "r", encoding="utf-8").read()
        stash_after_success = run_cmd("git rev-parse stash@{0}", tmpdir, check=False)
        stash_dropped = (stash_after_success.returncode != 0)

        # Fact 3: Smallest correction success
        assert good_pop_exit == 0, f"git stash pop failed after correction: {good_pop_res.stderr}"
        assert "stashed-line" in notes_content_after, "Stashed change 'stashed-line' missing from notes.txt"
        assert stash_dropped is True, "stash@{0} was not dropped after successful pop"

        # Fact 4: Ref persistence
        main_sha_final = run_cmd("git rev-parse main", tmpdir).stdout.strip()
        topic_sha_final = run_cmd("git rev-parse topic", tmpdir).stdout.strip()
        assert main_sha_final == commit_c, f"main ref moved: {main_sha_final} != {commit_c}"
        assert topic_sha_final == commit_b, f"topic ref moved: {topic_sha_final} != {commit_b}"

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
                "commit_c": {"branch": "main", "file": "todo.txt", "content": "one\n", "message": "Commit C"},
                "stashed_change": {"file": "notes.txt", "appended": "stashed-line\n"},
                "conflicting_local_edit": {"file": "notes.txt", "appended": "uncommitted-conflict\n"},
                "trigger_command": "git stash pop",
                "repair_command": "git checkout -- notes.txt && git stash pop"
            },
            "expected_results": {
                "fact_1": "Initial branch refs: main at Commit C, topic at Commit B",
                "fact_2": "Bad case: git stash pop fails with exit code != 0, notes.txt indicated in overwrite/conflict stderr, and stash@{0} is preserved",
                "fact_3": "Smallest correction: clearing conflicting edit allows git stash pop to exit 0, notes.txt contains 'stashed-line', and stash@{0} is dropped",
                "fact_4": "Ref persistence: main (Commit C) and topic (Commit B) remain unchanged throughout"
            },
            "actual_results": {
                "commit_ids": {
                    "commit_a": commit_a,
                    "commit_b": commit_b,
                    "commit_c": commit_c,
                    "original_stash_sha": stash_sha
                },
                "bad_case": {
                    "exit_code": bad_pop_exit,
                    "stderr": bad_pop_stderr,
                    "stash_still_present": stash_still_present
                },
                "correction_case": {
                    "exit_code": good_pop_exit,
                    "notes_content_has_stashed_line": "stashed-line" in notes_content_after,
                    "notes_content": notes_content_after,
                    "stash_dropped": stash_dropped
                },
                "ref_persistence": {
                    "main_final": main_sha_final,
                    "topic_final": topic_sha_final,
                    "main_matched": main_sha_final == commit_c,
                    "topic_matched": topic_sha_final == commit_b
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
