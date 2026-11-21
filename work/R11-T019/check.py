#!/usr/bin/env python3
r"""
Automated verification script for task R11-T019:
'Create new working tree from a repository (git 2.5)' (git worktree add -b)

Verifies:
1. Environment isolation:
   - GIT_CONFIG_NOSYSTEM=1
   - HOME pointed to an isolated temporary directory
   - Local git config user.name and user.email set in the repo
2. Precondition failure verification:
   - An unborn repository (no commits yet) fails when attempting git worktree add -b wt-fail <path> HEAD
3. Fixture construction on 'main':
   - Commit A: notes.txt = "alpha\n"
   - Commit B: notes.txt appended with "beta\n"
   - Branch 'topic' created at Commit B
   - Commit C on 'main': todo.txt = "one\n"
   - Stage a change in the primary worktree (notes.txt appended with "staged edit\n" and git add notes.txt)
4. Execute:
   - git worktree add -b wt-branch <wt_dir> topic
5. Assert 5 state facts using dynamic object IDs:
   (1) Prerequisites hold (--is-inside-work-tree == true, --is-bare-repository == false, HEAD == Commit C, wt-branch did not exist prior)
   (2) git worktree list --porcelain lists both primary worktree (main at Commit C) and new linked worktree (wt-branch at Commit B)
   (3) Inside <wt_dir>, HEAD equals Commit B, status is clean, notes.txt is "alpha\nbeta\n" (primary staged edit not leaked)
   (4) Inside primary worktree, main is at Commit C, topic is at Commit B, staged modification on notes.txt remains intact (git diff --cached --name-only == "notes.txt")
   (5) User's global Git configuration was untouched (GIT_CONFIG_NOSYSTEM=1 + isolated HOME confirmed)
6. Saves inputs, expected vs actual results, and git/python versions into work/R11-T019/results.json.
"""

import os
import sys
import json
import subprocess
import tempfile
import platform


def run_cmd(cmd: str, cwd: str, env: dict, check: bool = True) -> subprocess.CompletedProcess:
    """Executes a command using subprocess with custom isolated environment."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        check=check,
        env=env
    )


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results_path = os.path.join(script_dir, "results.json")

    git_ver = subprocess.run("git --version", shell=True, capture_output=True, text=True, check=True).stdout.strip()
    py_ver = sys.version.replace("\n", " ")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: Isolate Git configuration from user global config
        isolated_env = os.environ.copy()
        isolated_env["GIT_CONFIG_NOSYSTEM"] = "1"
        fake_home = os.path.join(tmpdir, "fake_home")
        os.makedirs(fake_home, exist_ok=True)
        isolated_env["HOME"] = fake_home

        # Step 2: Verify precondition failure on an unborn repo
        unborn_dir = os.path.join(tmpdir, "unborn_repo")
        os.makedirs(unborn_dir, exist_ok=True)
        run_cmd("git init -b main", unborn_dir, env=isolated_env, check=True)
        wt_fail_target = os.path.join(tmpdir, "wt_fail_dir")
        # Attempting to branch from HEAD in unborn repo must fail non-zero
        unborn_res = run_cmd(f"git worktree add -b wt-fail \"{wt_fail_target}\" HEAD", unborn_dir, env=isolated_env, check=False)
        assert unborn_res.returncode != 0, "git worktree add on unborn repo unexpectedly succeeded"

        # Step 3: Build fixture repo on main
        primary_dir = os.path.join(tmpdir, "primary_repo")
        os.makedirs(primary_dir, exist_ok=True)
        run_cmd("git init -b main", primary_dir, env=isolated_env, check=True)
        run_cmd("git config user.name \"Course Student\"", primary_dir, env=isolated_env, check=True)
        run_cmd("git config user.email \"student@example.invalid\"", primary_dir, env=isolated_env, check=True)

        # Commit A
        notes_file = os.path.join(primary_dir, "notes.txt")
        with open(notes_file, "w", encoding="utf-8") as f:
            f.write("alpha\n")
        run_cmd("git add notes.txt", primary_dir, env=isolated_env, check=True)
        run_cmd("git commit -m \"Commit A\"", primary_dir, env=isolated_env, check=True)
        commit_a = run_cmd("git rev-parse HEAD", primary_dir, env=isolated_env, check=True).stdout.strip()

        # Commit B
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write("beta\n")
        run_cmd("git add notes.txt", primary_dir, env=isolated_env, check=True)
        run_cmd("git commit -m \"Commit B\"", primary_dir, env=isolated_env, check=True)
        commit_b = run_cmd("git rev-parse HEAD", primary_dir, env=isolated_env, check=True).stdout.strip()

        # Branch topic at B
        run_cmd("git branch topic", primary_dir, env=isolated_env, check=True)

        # Commit C on main
        todo_file = os.path.join(primary_dir, "todo.txt")
        with open(todo_file, "w", encoding="utf-8") as f:
            f.write("one\n")
        run_cmd("git add todo.txt", primary_dir, env=isolated_env, check=True)
        run_cmd("git commit -m \"Commit C\"", primary_dir, env=isolated_env, check=True)
        commit_c = run_cmd("git rev-parse HEAD", primary_dir, env=isolated_env, check=True).stdout.strip()

        # Stage a modification in the primary worktree (verify it does NOT leak to new worktree)
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write("staged modification\n")
        run_cmd("git add notes.txt", primary_dir, env=isolated_env, check=True)

        # --- Assert Fact 1: Prerequisites hold ---
        is_inside_wt = run_cmd("git rev-parse --is-inside-work-tree", primary_dir, env=isolated_env, check=True).stdout.strip()
        is_bare = run_cmd("git rev-parse --is-bare-repository", primary_dir, env=isolated_env, check=True).stdout.strip()
        head_commit = run_cmd("git rev-parse HEAD", primary_dir, env=isolated_env, check=True).stdout.strip()
        branch_pre_check = run_cmd("git show-ref --verify --quiet refs/heads/wt-branch", primary_dir, env=isolated_env, check=False)

        assert is_inside_wt == "true", f"--is-inside-work-tree was {is_inside_wt}"
        assert is_bare == "false", f"--is-bare-repository was {is_bare}"
        assert head_commit == commit_c, f"HEAD {head_commit} != Commit C {commit_c}"
        assert branch_pre_check.returncode != 0, "Branch 'wt-branch' already existed prior to worktree add"

        # Step 4: Run git worktree add -b wt-branch <wt_dir> topic
        wt_dir = os.path.join(tmpdir, "wt_linked")
        wt_add_res = run_cmd(f"git worktree add -b wt-branch \"{wt_dir}\" topic", primary_dir, env=isolated_env, check=True)

        # --- Assert Fact 2: git worktree list --porcelain lists both worktrees ---
        wt_list_res = run_cmd("git worktree list --porcelain", primary_dir, env=isolated_env, check=True).stdout.strip()
        assert primary_dir in wt_list_res, "Primary repo missing from worktree list"
        assert wt_dir in wt_list_res, "Linked worktree missing from worktree list"
        assert commit_c in wt_list_res, f"Commit C SHA {commit_c} missing from worktree list"
        assert commit_b in wt_list_res, f"Commit B SHA {commit_b} missing from worktree list"

        # --- Assert Fact 3: Inside <wt_dir>, HEAD equals Commit B, status clean, notes.txt is "alpha\nbeta\n" ---
        wt_head = run_cmd("git rev-parse HEAD", wt_dir, env=isolated_env, check=True).stdout.strip()
        wt_status = run_cmd("git status --porcelain", wt_dir, env=isolated_env, check=True).stdout.strip()
        wt_notes_content = open(os.path.join(wt_dir, "notes.txt"), "r", encoding="utf-8").read()

        assert wt_head == commit_b, f"Worktree HEAD {wt_head} != Commit B {commit_b}"
        assert wt_status == "", f"Worktree status is not clean:\n{wt_status}"
        assert wt_notes_content == "alpha\nbeta\n", f"Worktree notes.txt content corrupted: {repr(wt_notes_content)}"

        # --- Assert Fact 4: Inside primary worktree, main at C, topic at B, staged notes.txt intact ---
        primary_main = run_cmd("git rev-parse main", primary_dir, env=isolated_env, check=True).stdout.strip()
        primary_topic = run_cmd("git rev-parse topic", primary_dir, env=isolated_env, check=True).stdout.strip()
        primary_staged = run_cmd("git diff --cached --name-only", primary_dir, env=isolated_env, check=True).stdout.strip()

        assert primary_main == commit_c, f"Primary main ref moved: {primary_main} != {commit_c}"
        assert primary_topic == commit_b, f"Primary topic ref moved: {primary_topic} != {commit_b}"
        assert primary_staged == "notes.txt", f"Staged change in primary worktree lost: {primary_staged}"

        # --- Assert Fact 5: User's global Git config untouched ---
        assert isolated_env["GIT_CONFIG_NOSYSTEM"] == "1"
        assert isolated_env["HOME"] == fake_home
        assert not os.path.exists(os.path.join(fake_home, ".gitconfig")), "Global config created in isolated home"

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
                "primary_staged_change": {"file": "notes.txt", "appended": "staged modification\n"},
                "worktree_command": f"git worktree add -b wt-branch \"{wt_dir}\" topic",
                "environment_isolation": {
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "isolated_HOME": fake_home
                }
            },
            "expected_results": {
                "fact_1": "Prerequisites hold (--is-inside-work-tree == true, --is-bare-repository == false, HEAD == Commit C, wt-branch did not exist prior)",
                "fact_2": "git worktree list --porcelain lists both primary worktree (main at Commit C) and new linked worktree (wt-branch at Commit B)",
                "fact_3": "Inside <wt_dir>, HEAD equals Commit B, status is clean, notes.txt is 'alpha\\nbeta\\n' (primary staged edit not leaked)",
                "fact_4": "Inside primary worktree, main is at Commit C, topic is at Commit B, staged modification on notes.txt remains intact",
                "fact_5": "User's global Git configuration was untouched (GIT_CONFIG_NOSYSTEM=1 + isolated HOME confirmed)"
            },
            "actual_results": {
                "commit_ids": {
                    "commit_a": commit_a,
                    "commit_b": commit_b,
                    "commit_c": commit_c
                },
                "precondition_failure_check": {
                    "command": f"git worktree add -b wt-fail \"{wt_fail_target}\" HEAD",
                    "exit_code": unborn_res.returncode,
                    "stderr": unborn_res.stderr.strip()
                },
                "prerequisites_check": {
                    "is_inside_work_tree": is_inside_wt,
                    "is_bare_repository": is_bare,
                    "head_commit": head_commit,
                    "branch_did_not_exist_prior": branch_pre_check.returncode != 0
                },
                "worktree_list_porcelain": wt_list_res,
                "linked_worktree_state": {
                    "path": wt_dir,
                    "head_sha": wt_head,
                    "status_clean": wt_status == "",
                    "notes_content": wt_notes_content
                },
                "primary_worktree_state": {
                    "main_sha": primary_main,
                    "topic_sha": primary_topic,
                    "cached_diff": primary_staged
                },
                "global_isolation_confirmed": True,
                "assertions_passed": True
            }
        }

        os.makedirs(os.path.dirname(results_path), exist_ok=True)
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)

        print("All 5 state facts verified successfully.")
        print(f"Saved results to {results_path}")


if __name__ == "__main__":
    main()
