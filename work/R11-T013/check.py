#!/usr/bin/env python3
r"""
Automated verification script for task R11-T013:
'List all git aliases' with Recovery workflow

Verifies:
1. Setup scenario:
   - Init repo on 'main'
   - Author: 'Course Student <student@example.invalid>'
   - Commit A: notes.txt = "alpha\n"
   - Commit B: notes.txt appended with "beta\n"
   - Create branch topic at B
   - Commit C: todo.txt = "one\n"
2. Record original Commit C SHA and HEAD^{tree} hash.
3. Configure local alias 'alias.wipe = reset --hard HEAD~1'.
4. List aliases using exact command anchors:
   - git config -l | grep alias | sed 's/^alias\.//g'
   - git config -l | grep alias | cut -d '.' -f 2
5. Simulate reversible mistake:
   - Overwrite alias: git config --local alias.wipe "status"
   - Invoke mistake alias rollback: git reset --hard HEAD~1 (rolling back main from C to B)
6. Recovery:
   - Restore original alias: git config --local alias.wipe "reset --hard HEAD~1"
   - Recover Commit C / tree state via git reflog + git reset --hard <commit_c_sha>
7. Assert at least 4 state facts:
   (1) Alias listing anchors accurately reflect configured/overwritten/restored aliases
   (2) Mistake moved HEAD away from C (dropping todo.txt)
   (3) Recovery restores HEAD to exact dynamic commit C SHA
   (4) Recovered HEAD^{tree} hash and file contents (notes.txt, todo.txt) match original C
8. Saves inputs, expected vs actual results, and git/python versions into work/R11-T013/results.json.
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
        # Step 1: Initialize branch main and configure author
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

        # Step 4: Create branch topic at B
        run_cmd("git branch topic", tmpdir)

        # Step 5: Commit C on main (todo.txt = "one\n")
        todo_file = os.path.join(tmpdir, "todo.txt")
        with open(todo_file, "w", encoding="utf-8") as f:
            f.write("one\n")
        run_cmd("git add todo.txt", tmpdir)
        run_cmd("git commit -m \"Commit C\"", tmpdir)
        commit_c = run_cmd("git rev-parse HEAD", tmpdir)
        tree_c = run_cmd("git rev-parse HEAD^{tree}", tmpdir)

        # Step 6: Configure local alias
        alias_def = "reset --hard HEAD~1"
        run_cmd(f"git config --local alias.wipe \"{alias_def}\"", tmpdir)

        # Test listing aliases using exact command anchors
        anchor_sed_cmd = "git config -l | grep alias | sed 's/^alias\\.//g'"
        anchor_cut_cmd = "git config -l | grep alias | cut -d '.' -f 2"

        anchor_sed_configured = run_cmd(anchor_sed_cmd, tmpdir)
        anchor_cut_configured = run_cmd(anchor_cut_cmd, tmpdir)

        # Step 7: Simulate reversible mistake
        # 7a. Execute destructive alias rollback (rolling back main from C to B)
        run_cmd("git wipe", tmpdir)
        mistake_head = run_cmd("git rev-parse HEAD", tmpdir)
        mistake_todo_exists = os.path.exists(todo_file)
        mistake_tree = run_cmd("git rev-parse HEAD^{tree}", tmpdir)

        # 7b. Overwrite alias
        run_cmd("git config --local alias.wipe \"status\"", tmpdir)
        anchor_sed_overwritten = run_cmd(anchor_sed_cmd, tmpdir)
        anchor_cut_overwritten = run_cmd(anchor_cut_cmd, tmpdir)

        # Step 8: Recovery
        # 8a. Restore original alias definition
        run_cmd(f"git config --local alias.wipe \"{alias_def}\"", tmpdir)
        anchor_sed_restored = run_cmd(anchor_sed_cmd, tmpdir)
        anchor_cut_restored = run_cmd(anchor_cut_cmd, tmpdir)

        # 8b. Inspect reflog and recover Commit C via git reset --hard
        reflog_output = run_cmd("git reflog", tmpdir)
        run_cmd(f"git reset --hard {commit_c}", tmpdir)

        recovered_head = run_cmd("git rev-parse HEAD", tmpdir)
        recovered_tree = run_cmd("git rev-parse HEAD^{tree}", tmpdir)
        recovered_todo_exists = os.path.exists(todo_file)
        with open(notes_file, "r", encoding="utf-8") as f:
            recovered_notes_content = f.read()
        with open(todo_file, "r", encoding="utf-8") as f:
            recovered_todo_content = f.read()

        # Assertions for 4 State Facts:
        # Fact 1: Alias listing anchors accurately reflect configured, overwritten, restored aliases
        assert "wipe=reset --hard HEAD~1" in anchor_sed_configured, "Anchor sed did not reflect configured alias"
        assert "wipe=reset --hard HEAD~1" in anchor_cut_configured, "Anchor cut did not reflect configured alias"
        assert "wipe=status" in anchor_sed_overwritten, "Anchor sed did not reflect overwritten alias"
        assert "wipe=status" in anchor_cut_overwritten, "Anchor cut did not reflect overwritten alias"
        assert "wipe=reset --hard HEAD~1" in anchor_sed_restored, "Anchor sed did not reflect restored alias"
        assert "wipe=reset --hard HEAD~1" in anchor_cut_restored, "Anchor cut did not reflect restored alias"

        # Fact 2: Mistake moved HEAD away from C (dropping todo.txt)
        assert mistake_head == commit_b, f"Mistake HEAD {mistake_head} != Commit B {commit_b}"
        assert mistake_head != commit_c, "Mistake HEAD unexpectedly equals Commit C"
        assert mistake_todo_exists is False, "todo.txt still exists after destructive rollback"

        # Fact 3: Recovery restores HEAD to exact dynamic commit C SHA
        assert recovered_head == commit_c, f"Recovered HEAD {recovered_head} != Commit C {commit_c}"

        # Fact 4: Recovered HEAD^{tree} hash and file contents match original C
        assert recovered_tree == tree_c, f"Recovered tree {recovered_tree} != original tree {tree_c}"
        assert recovered_todo_exists is True, "todo.txt missing after recovery"
        assert recovered_notes_content == "alpha\nbeta\n", "notes.txt content corrupted after recovery"
        assert recovered_todo_content == "one\n", "todo.txt content corrupted after recovery"

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
                "configured_alias": {"name": "alias.wipe", "command": "reset --hard HEAD~1"},
                "overwritten_alias": {"name": "alias.wipe", "command": "status"},
                "anchor_commands": {
                    "sed": anchor_sed_cmd,
                    "cut": anchor_cut_cmd
                }
            },
            "expected_results": {
                "fact_1_alias_anchors": "Listing anchors match 'wipe=reset --hard HEAD~1' when configured, 'wipe=status' when overwritten, and restored definition",
                "fact_2_mistake_effect": "Invoking alias moves HEAD from Commit C to Commit B and removes todo.txt from working tree",
                "fact_3_recovered_head": "Recovery via reflog + git reset --hard restores HEAD to dynamic Commit C SHA",
                "fact_4_recovered_tree_and_files": "Recovered HEAD^{tree} matches original tree_c; notes.txt contains 'alpha\\nbeta\\n', todo.txt contains 'one\\n'"
            },
            "actual_results": {
                "commit_ids": {
                    "commit_a": commit_a,
                    "commit_b": commit_b,
                    "commit_c": commit_c,
                    "tree_c": tree_c
                },
                "anchor_outputs": {
                    "configured_sed": anchor_sed_configured,
                    "configured_cut": anchor_cut_configured,
                    "overwritten_sed": anchor_sed_overwritten,
                    "overwritten_cut": anchor_cut_overwritten,
                    "restored_sed": anchor_sed_restored,
                    "restored_cut": anchor_cut_restored
                },
                "mistake_state": {
                    "head": mistake_head,
                    "tree": mistake_tree,
                    "todo_exists": mistake_todo_exists
                },
                "recovered_state": {
                    "head": recovered_head,
                    "tree": recovered_tree,
                    "todo_exists": recovered_todo_exists,
                    "notes_content": recovered_notes_content,
                    "todo_content": recovered_todo_content
                },
                "reflog_sample": reflog_output.splitlines()[:5],
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
