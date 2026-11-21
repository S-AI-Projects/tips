#!/usr/bin/env python3
r"""
Automated verification script for task R11-T016:
'Force push to Remote Repository' (git push -f vs git push --force-with-lease)

Verifies:
1. Builds two equivalent fixtures with local bare remotes:
   - Commit A: notes.txt = "alpha\n"
   - Commit B: notes.txt appended with "beta\n"
   - Branch 'topic' created at Commit B
   - Commit C on 'main': todo.txt = "one\n" pushed to origin/main
   - Secondary clone pushes concurrent commit D to origin/main
   - Local working repo resets/rewrites main at B to B_rewritten
2. Fixture 1: Runs 'git push -f origin main' (succeeds, overwrites D to B_rewritten).
3. Fixture 2: Runs 'git push --force-with-lease origin main' (fails with 'stale info', preserves D).
4. Asserts 4 state facts using dynamic object IDs:
   (1) Both fixtures start from identical commit/tree structures (A, B, C, D, B_rewritten)
   (2) In Fixture 1, git push -f exits 0 and remote main ref becomes B_rewritten (overwriting D)
   (3) In Fixture 2, git push --force-with-lease exits non-zero with 'stale info' and remote main ref stays at D
   (4) Local main (B_rewritten), topic (B), HEAD^{tree}, index, and git status --porcelain remain clean/unchanged after the push attempts
5. Saves inputs, expected vs actual results, and git/python versions into work/R11-T016/results.json.
"""

import os
import sys
import json
import subprocess
import tempfile
import platform


def run_cmd(cmd: str, cwd: str, env: dict = None, check: bool = True) -> subprocess.CompletedProcess:
    """Executes a command using subprocess and returns CompletedProcess."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        check=check,
        env=env
    )


def build_fixture(base_dir: str) -> dict:
    os.makedirs(base_dir, exist_ok=True)

    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Course Student"
    env["GIT_AUTHOR_EMAIL"] = "student@example.invalid"
    env["GIT_COMMITTER_NAME"] = "Course Student"
    env["GIT_COMMITTER_EMAIL"] = "student@example.invalid"

    bare_dir = os.path.join(base_dir, "remote.git")
    run_cmd(f"git init -b main --bare \"{bare_dir}\"", base_dir)

    work_dir = os.path.join(base_dir, "work_repo")
    os.makedirs(work_dir)
    run_cmd("git init -b main", work_dir)
    run_cmd(f"git remote add origin \"file://{bare_dir}\"", work_dir)

    # Commit A
    env["GIT_AUTHOR_DATE"] = "2026-01-01T00:01:00Z"
    env["GIT_COMMITTER_DATE"] = "2026-01-01T00:01:00Z"
    with open(os.path.join(work_dir, "notes.txt"), "w", encoding="utf-8") as f:
        f.write("alpha\n")
    run_cmd("git add notes.txt", work_dir)
    run_cmd("git commit -m \"Commit A\"", work_dir, env=env)
    commit_a = run_cmd("git rev-parse HEAD", work_dir).stdout.strip()

    # Commit B
    env["GIT_AUTHOR_DATE"] = "2026-01-01T00:02:00Z"
    env["GIT_COMMITTER_DATE"] = "2026-01-01T00:02:00Z"
    with open(os.path.join(work_dir, "notes.txt"), "a", encoding="utf-8") as f:
        f.write("beta\n")
    run_cmd("git add notes.txt", work_dir)
    run_cmd("git commit -m \"Commit B\"", work_dir, env=env)
    commit_b = run_cmd("git rev-parse HEAD", work_dir).stdout.strip()

    # Branch topic at B
    run_cmd("git branch topic", work_dir)

    # Commit C on main
    env["GIT_AUTHOR_DATE"] = "2026-01-01T00:03:00Z"
    env["GIT_COMMITTER_DATE"] = "2026-01-01T00:03:00Z"
    with open(os.path.join(work_dir, "todo.txt"), "w", encoding="utf-8") as f:
        f.write("one\n")
    run_cmd("git add todo.txt", work_dir)
    run_cmd("git commit -m \"Commit C\"", work_dir, env=env)
    commit_c = run_cmd("git rev-parse HEAD", work_dir).stdout.strip()
    run_cmd("git push -u origin main", work_dir)

    # Secondary clone: push concurrent commit D to origin/main
    secondary_dir = os.path.join(base_dir, "secondary")
    run_cmd(f"git clone \"file://{bare_dir}\" \"{secondary_dir}\"", base_dir)
    sec_env = env.copy()
    sec_env["GIT_AUTHOR_NAME"] = "Teammate"
    sec_env["GIT_AUTHOR_EMAIL"] = "teammate@example.invalid"
    sec_env["GIT_COMMITTER_NAME"] = "Teammate"
    sec_env["GIT_COMMITTER_EMAIL"] = "teammate@example.invalid"
    sec_env["GIT_AUTHOR_DATE"] = "2026-01-01T00:04:00Z"
    sec_env["GIT_COMMITTER_DATE"] = "2026-01-01T00:04:00Z"
    with open(os.path.join(secondary_dir, "concurrent.txt"), "w", encoding="utf-8") as f:
        f.write("concurrent D\n")
    run_cmd("git add concurrent.txt", secondary_dir)
    run_cmd("git commit -m \"Commit D\"", secondary_dir, env=sec_env)
    commit_d = run_cmd("git rev-parse HEAD", secondary_dir).stdout.strip()
    run_cmd("git push origin main", secondary_dir)

    # In work_repo: rewrite local main at B to B_rewritten
    run_cmd("git reset --hard HEAD~1", work_dir)
    env["GIT_AUTHOR_DATE"] = "2026-01-01T00:05:00Z"
    env["GIT_COMMITTER_DATE"] = "2026-01-01T00:05:00Z"
    with open(os.path.join(work_dir, "rewritten.txt"), "w", encoding="utf-8") as f:
        f.write("rewritten\n")
    run_cmd("git add rewritten.txt", work_dir)
    run_cmd("git commit -m \"Commit B_rewritten\"", work_dir, env=env)
    commit_b_rewritten = run_cmd("git rev-parse HEAD", work_dir).stdout.strip()
    tree_b_rewritten = run_cmd("git rev-parse HEAD^{tree}", work_dir).stdout.strip()

    return {
        "bare_dir": bare_dir,
        "work_dir": work_dir,
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "commit_d": commit_d,
        "commit_b_rewritten": commit_b_rewritten,
        "tree_b_rewritten": tree_b_rewritten,
        "env": env
    }


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results_path = os.path.join(script_dir, "results.json")

    git_ver = run_cmd("git --version", ".").stdout.strip()
    py_ver = sys.version.replace("\n", " ")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Build two equivalent fixtures
        f1 = build_fixture(os.path.join(tmpdir, "fixture_1"))
        f2 = build_fixture(os.path.join(tmpdir, "fixture_2"))

        # Fact 1: Both fixtures start from identical commit/tree structures (A, B, C, D, B_rewritten)
        assert f1["commit_a"] == f2["commit_a"], "Commit A mismatch between fixtures"
        assert f1["commit_b"] == f2["commit_b"], "Commit B mismatch between fixtures"
        assert f1["commit_c"] == f2["commit_c"], "Commit C mismatch between fixtures"
        assert f1["commit_d"] == f2["commit_d"], "Commit D mismatch between fixtures"
        assert f1["commit_b_rewritten"] == f2["commit_b_rewritten"], "Commit B_rewritten mismatch between fixtures"
        assert f1["tree_b_rewritten"] == f2["tree_b_rewritten"], "Tree B_rewritten mismatch between fixtures"

        # Record pre-push states in work repos
        f1_topic_pre = run_cmd("git rev-parse topic", f1["work_dir"]).stdout.strip()
        f2_topic_pre = run_cmd("git rev-parse topic", f2["work_dir"]).stdout.strip()
        assert f1_topic_pre == f1["commit_b"]
        assert f2_topic_pre == f2["commit_b"]

        # Fixture 1: Run git push -f origin main
        f1_res = run_cmd("git push -f origin main", f1["work_dir"], check=True)
        f1_remote_main = run_cmd("git rev-parse main", f1["bare_dir"]).stdout.strip()

        # Fact 2: In Fixture 1, git push -f exits 0 and remote main ref becomes B_rewritten (overwriting D)
        assert f1_res.returncode == 0, f"git push -f failed with exit code {f1_res.returncode}"
        assert f1_remote_main == f1["commit_b_rewritten"], f"Remote main {f1_remote_main} != B_rewritten {f1['commit_b_rewritten']}"
        assert f1_remote_main != f1["commit_d"], "Remote main still points to D after force push"

        # Fixture 2: Run git push --force-with-lease origin main
        f2_res = run_cmd("git push --force-with-lease origin main", f2["work_dir"], check=False)
        f2_remote_main = run_cmd("git rev-parse main", f2["bare_dir"]).stdout.strip()

        # Fact 3: In Fixture 2, git push --force-with-lease exits non-zero with 'stale info' and remote main ref stays at D
        assert f2_res.returncode != 0, "git push --force-with-lease unexpectedly succeeded"
        assert "stale info" in f2_res.stderr, f"'stale info' missing from stderr:\n{f2_res.stderr}"
        assert f2_remote_main == f2["commit_d"], f"Remote main {f2_remote_main} != Commit D {f2['commit_d']}"

        # Fact 4: Local main (B_rewritten), topic (B), HEAD^{tree}, index, and git status --porcelain remain clean/unchanged
        for f_name, f in [("Fixture 1", f1), ("Fixture 2", f2)]:
            local_main = run_cmd("git rev-parse HEAD", f["work_dir"]).stdout.strip()
            local_topic = run_cmd("git rev-parse topic", f["work_dir"]).stdout.strip()
            local_tree = run_cmd("git rev-parse HEAD^{tree}", f["work_dir"]).stdout.strip()
            status_porcelain = run_cmd("git status --porcelain", f["work_dir"]).stdout.strip()
            diff_unstaged = run_cmd("git diff", f["work_dir"]).stdout.strip()
            diff_cached = run_cmd("git diff --cached", f["work_dir"]).stdout.strip()

            assert local_main == f["commit_b_rewritten"], f"{f_name}: local main altered"
            assert local_topic == f["commit_b"], f"{f_name}: local topic altered"
            assert local_tree == f["tree_b_rewritten"], f"{f_name}: local tree altered"
            assert status_porcelain == "", f"{f_name}: working tree dirty"
            assert diff_unstaged == "", f"{f_name}: unstaged diff present"
            assert diff_cached == "", f"{f_name}: staged diff present"

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
                "commit_d_concurrent": {"author": "Teammate", "file": "concurrent.txt", "content": "concurrent D\n", "message": "Commit D"},
                "commit_b_rewritten": {"reset_to": "Commit B", "file": "rewritten.txt", "content": "rewritten\n", "message": "Commit B_rewritten"},
                "fixture_1_command": "git push -f origin main",
                "fixture_2_command": "git push --force-with-lease origin main"
            },
            "expected_results": {
                "fact_1": "Both fixtures start from identical commit/tree structures (A, B, C, D, B_rewritten)",
                "fact_2": "In Fixture 1, git push -f exits 0 and remote main ref becomes B_rewritten (overwriting D)",
                "fact_3": "In Fixture 2, git push --force-with-lease exits non-zero with 'stale info' and remote main ref stays at D",
                "fact_4": "Local main (B_rewritten), topic (B), HEAD^{tree}, index, and git status --porcelain remain clean/unchanged after push attempts"
            },
            "actual_results": {
                "fixture_commit_ids": {
                    "commit_a": f1["commit_a"],
                    "commit_b": f1["commit_b"],
                    "commit_c": f1["commit_c"],
                    "commit_d": f1["commit_d"],
                    "commit_b_rewritten": f1["commit_b_rewritten"],
                    "tree_b_rewritten": f1["tree_b_rewritten"]
                },
                "fixture_1": {
                    "command": "git push -f origin main",
                    "exit_code": f1_res.returncode,
                    "remote_main_after": f1_remote_main,
                    "remote_overwritten_to_b_rewritten": f1_remote_main == f1["commit_b_rewritten"]
                },
                "fixture_2": {
                    "command": "git push --force-with-lease origin main",
                    "exit_code": f2_res.returncode,
                    "stderr": f2_res.stderr.strip(),
                    "remote_main_after": f2_remote_main,
                    "remote_preserved_at_d": f2_remote_main == f2["commit_d"]
                },
                "local_state_verification": {
                    "fixture_1_clean": True,
                    "fixture_2_clean": True,
                    "main_at_b_rewritten": True,
                    "topic_at_b": True
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
