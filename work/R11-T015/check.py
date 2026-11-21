#!/usr/bin/env python3
r"""
Automated verification script for task R11-T015:
'Fetch pull request by ID to a local branch' with Quoted Path and '--' Disambiguation

Verifies:
1. Setup scenario:
   - Bare remote repository ('remote.git') via file:// URL
   - Working repo on 'main'
   - Author: 'Course Student <student@example.invalid>'
   - Commit A: notes.txt = "alpha\n"
   - Commit B: notes.txt appended with "beta\n"
   - Branch 'topic' created at Commit B
   - Commit C on 'main': todo.txt = "one\n"
   - Push 'main' to local 'origin'
2. In secondary clone / branch:
   - Add 'release notes.txt' and 'sample data/release notes.txt' (paths containing spaces)
   - Push to refs/pull/15/head on bare remote
3. In working repo:
   - Fetch PR ref using exact command anchor: git fetch origin pull/15/head:pr-15
   - Verify quoted path handling and '--' disambiguation
4. Assert at least 4 state facts using dynamic object IDs:
   (1) git rev-parse pr-15 matches exact dynamic commit SHA pushed to refs/pull/15/head
   (2) git diff --name-only main pr-15 -- "sample data/release notes.txt" and "release notes.txt"
       preserve spaces and act on the exact intended files
   (3) Unquoted/unseparated ambiguity test (git diff with split tokens ["release", "notes.txt"] or missing '--')
       fails non-zero with 'ambiguous argument' in stderr
   (4) Checking out pr-15 -- "sample data/release notes.txt" materializes the exact file with spaces intact
       while keeping main at Commit C and topic at Commit B
5. Saves inputs, expected vs actual results, and git/python versions into work/R11-T015/results.json.
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
        # Step 1: Initialize bare remote
        bare_dir = os.path.join(tmpdir, "remote.git")
        run_cmd(f"git init --bare \"{bare_dir}\"", tmpdir)

        # Step 2: Initialize working repo
        repo_dir = os.path.join(tmpdir, "repo")
        os.makedirs(repo_dir)

        run_cmd("git init -b main", repo_dir)
        run_cmd("git config user.name \"Course Student\"", repo_dir)
        run_cmd("git config user.email \"student@example.invalid\"", repo_dir)
        run_cmd(f"git remote add origin \"file://{bare_dir}\"", repo_dir)

        # Commit A (notes.txt = "alpha\n")
        notes_file = os.path.join(repo_dir, "notes.txt")
        with open(notes_file, "w", encoding="utf-8") as f:
            f.write("alpha\n")
        run_cmd("git add notes.txt", repo_dir)
        run_cmd("git commit -m \"Commit A\"", repo_dir)
        commit_a = run_cmd("git rev-parse HEAD", repo_dir).stdout.strip()

        # Commit B (notes.txt appended with "beta\n")
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write("beta\n")
        run_cmd("git add notes.txt", repo_dir)
        run_cmd("git commit -m \"Commit B\"", repo_dir)
        commit_b = run_cmd("git rev-parse HEAD", repo_dir).stdout.strip()

        # Branch topic at Commit B
        run_cmd("git branch topic", repo_dir)

        # Commit C on main (todo.txt = "one\n")
        todo_file = os.path.join(repo_dir, "todo.txt")
        with open(todo_file, "w", encoding="utf-8") as f:
            f.write("one\n")
        run_cmd("git add todo.txt", repo_dir)
        run_cmd("git commit -m \"Commit C\"", repo_dir)
        commit_c = run_cmd("git rev-parse HEAD", repo_dir).stdout.strip()

        # Push main to origin
        run_cmd("git push -u origin main", repo_dir)

        # Step 3: Secondary clone to push PR commits to refs/pull/15/head
        pr_clone_dir = os.path.join(tmpdir, "pr_clone")
        run_cmd(f"git clone \"file://{bare_dir}\" \"{pr_clone_dir}\"", tmpdir)
        run_cmd("git config user.name \"PR Author\"", pr_clone_dir)
        run_cmd("git config user.email \"pr@example.invalid\"", pr_clone_dir)

        rel_notes = os.path.join(pr_clone_dir, "release notes.txt")
        with open(rel_notes, "w", encoding="utf-8") as f:
            f.write("release notes content v1.5\n")

        sample_dir = os.path.join(pr_clone_dir, "sample data")
        os.makedirs(sample_dir, exist_ok=True)
        sample_rel_notes = os.path.join(sample_dir, "release notes.txt")
        with open(sample_rel_notes, "w", encoding="utf-8") as f:
            f.write("sample data release notes content v1.5\n")

        run_cmd("git add \"release notes.txt\" \"sample data/release notes.txt\"", pr_clone_dir)
        run_cmd("git commit -m \"PR 15: add release notes with spaces\"", pr_clone_dir)
        pr_commit_sha = run_cmd("git rev-parse HEAD", pr_clone_dir).stdout.strip()
        run_cmd("git push origin HEAD:refs/pull/15/head", pr_clone_dir)

        # Step 4: In working repo, fetch PR using exact anchor
        fetch_cmd = "git fetch origin pull/15/head:pr-15"
        fetch_res = run_cmd(fetch_cmd, repo_dir)
        pr15_sha = run_cmd("git rev-parse pr-15", repo_dir).stdout.strip()

        # Diff commands with quoted paths and '--'
        diff_cmd_sample = "git diff --name-only main pr-15 -- \"sample data/release notes.txt\""
        diff_res_sample = run_cmd(diff_cmd_sample, repo_dir).stdout.strip()

        diff_cmd_root = "git diff --name-only main pr-15 -- \"release notes.txt\""
        diff_res_root = run_cmd(diff_cmd_root, repo_dir).stdout.strip()

        # Step 5: Test unquoted/unseparated ambiguity failure
        # Unquoted path 'release notes.txt' splits into arguments 'release' and 'notes.txt'
        split_cmd = "git diff main pr-15 release notes.txt"
        split_res = run_cmd(split_cmd, repo_dir, check=False)

        # Ambiguity test with collision and missing '--'
        # e.g., create a branch named 'notes.txt' matching existing filename 'notes.txt'
        run_cmd("git branch notes.txt main", repo_dir)
        collision_cmd = "git log notes.txt"
        collision_res = run_cmd(collision_cmd, repo_dir, check=False)

        # Step 6: Checkout pr-15 -- "sample data/release notes.txt"
        checkout_cmd = "git checkout pr-15 -- \"sample data/release notes.txt\""
        run_cmd(checkout_cmd, repo_dir)

        materialized_path = os.path.join(repo_dir, "sample data", "release notes.txt")
        materialized_exists = os.path.exists(materialized_path)
        materialized_content = open(materialized_path, "r", encoding="utf-8").read() if materialized_exists else ""

        main_ref_after = run_cmd("git rev-parse main", repo_dir).stdout.strip()
        topic_ref_after = run_cmd("git rev-parse topic", repo_dir).stdout.strip()

        # --- Assertions (at least 4 state facts) ---
        # Fact 1: git rev-parse pr-15 matches exact dynamic commit SHA pushed to refs/pull/15/head
        assert pr15_sha == pr_commit_sha, f"pr-15 SHA {pr15_sha} != PR commit SHA {pr_commit_sha}"

        # Fact 2: git diff --name-only main pr-15 -- "sample data/release notes.txt" and "release notes.txt"
        # preserve spaces and act on exact intended files
        assert diff_res_sample == "sample data/release notes.txt", f"diff sample output mismatch: {diff_res_sample}"
        assert diff_res_root == "release notes.txt", f"diff root output mismatch: {diff_res_root}"

        # Fact 3: Unquoted/unseparated ambiguity test fails non-zero with 'ambiguous argument' in stderr
        assert split_res.returncode != 0, "Unquoted split command unexpectedly succeeded"
        assert "ambiguous argument" in split_res.stderr, f"'ambiguous argument' missing in stderr:\n{split_res.stderr}"
        assert "release" in split_res.stderr, f"'release' token missing in stderr:\n{split_res.stderr}"

        assert collision_res.returncode != 0, "Collision command without '--' unexpectedly succeeded"
        assert "ambiguous argument" in collision_res.stderr, f"'ambiguous argument' missing in collision stderr:\n{collision_res.stderr}"

        # Fact 4: Checking out pr-15 -- "sample data/release notes.txt" materializes exact file with spaces intact
        # while keeping main at Commit C and topic at Commit B
        assert materialized_exists is True, "Sample data release notes file was not materialized"
        assert materialized_content == "sample data release notes content v1.5\n", "Materialized content corrupted"
        assert main_ref_after == commit_c, f"main ref moved: {main_ref_after} != {commit_c}"
        assert topic_ref_after == commit_b, f"topic ref moved: {topic_ref_after} != {commit_b}"

        results_data = {
            "tool_versions": {
                "git": git_ver,
                "python": py_ver,
                "platform": platform.platform()
            },
            "inputs": {
                "bare_remote": f"file://{bare_dir}",
                "author": "Course Student <student@example.invalid>",
                "initial_branch": "main",
                "commit_a": {"file": "notes.txt", "content": "alpha\n", "message": "Commit A"},
                "commit_b": {"file": "notes.txt", "content_appended": "beta\n", "message": "Commit B"},
                "branch_topic": {"fork_point": "Commit B"},
                "commit_c": {"branch": "main", "file": "todo.txt", "content": "one\n", "message": "Commit C"},
                "pr_ref": "refs/pull/15/head",
                "pr_files_with_spaces": [
                    "release notes.txt",
                    "sample data/release notes.txt"
                ],
                "anchor_fetch_command": fetch_cmd,
                "checkout_command": checkout_cmd
            },
            "expected_results": {
                "fact_1": "git rev-parse pr-15 matches exact dynamic commit SHA pushed to refs/pull/15/head",
                "fact_2": "git diff --name-only main pr-15 with quoted paths preserves spaces and returns 'sample data/release notes.txt' and 'release notes.txt'",
                "fact_3": "Unquoted split command fails with non-zero exit code and 'ambiguous argument' error in stderr",
                "fact_4": "Checking out pr-15 -- 'sample data/release notes.txt' materializes file with spaces while main stays at Commit C and topic stays at Commit B"
            },
            "actual_results": {
                "commit_ids": {
                    "commit_a": commit_a,
                    "commit_b": commit_b,
                    "commit_c": commit_c,
                    "pr_commit": pr_commit_sha,
                    "pr15_ref_sha": pr15_sha
                },
                "diff_outputs": {
                    "sample_data_file": diff_res_sample,
                    "root_file": diff_res_root
                },
                "ambiguity_test": {
                    "command": split_cmd,
                    "exit_code": split_res.returncode,
                    "stderr": split_res.stderr.strip()
                },
                "ref_and_tree_state": {
                    "materialized_file": "sample data/release notes.txt",
                    "materialized_content": materialized_content,
                    "main_ref": main_ref_after,
                    "topic_ref": topic_ref_after
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
