#!/usr/bin/env python3
"""
Verification script for GitHub Task R11-T040.
Task: Add a prediction-and-verification exercise: Always rebase instead of merge on pull.
Issue: https://github.com/S-AI-Projects/tips/issues/42

Verifies:
1. Isolated temporary working and bare remote repositories with file:// URL.
2. Initial branch 'main' with author 'Course Student <student@example.invalid>'.
3. Commits A ('alpha\\n'), B ('alpha\\nbeta\\n'), branch 'topic' at B, Commit C ('one\\n').
4. Configuration of branch.autosetuprebase always.
5. Topic tracking origin/main automatically sets branch.topic.rebase to true.
6. Diverged histories between local topic and updated remote main.
7. Configuration of pull.rebase true.
8. Execution of git pull rebasing local topic commit onto remote commit C without merge commit.
9. Assertions verifying 10 meaningful Git state facts.
"""

import os
import sys
import json
import tempfile
import subprocess
import platform
from pathlib import Path

out_dir = Path(__file__).resolve().parent


def run_git(args, cwd, env):
    """Run a git command in cwd with isolated env, checking returncode."""
    res = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return res.stdout.strip()


def main():
    with tempfile.TemporaryDirectory() as tmp_root:
        root = Path(tmp_root)
        repo_dir = root / "repo"
        remote_dir = root / "remote.git"
        home_dir = root / "home"
        home_dir.mkdir(parents=True, exist_ok=True)

        # Isolated environment: empty home and isolated git config
        env = os.environ.copy()
        env.update({
            "HOME": str(home_dir),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(home_dir / ".gitconfig"),
        })

        # 1. Initialize bare remote repository
        subprocess.run(
            ["git", "init", "--bare", "-b", "main", str(remote_dir)],
            check=True,
            capture_output=True,
        )

        # 2. Initialize local repository on branch main
        subprocess.run(
            ["git", "init", "-b", "main", str(repo_dir)],
            check=True,
            capture_output=True,
        )

        # Configure local user identity
        run_git(["config", "user.name", "Course Student"], repo_dir, env)
        run_git(["config", "user.email", "student@example.invalid"], repo_dir, env)

        # Commit A: create notes.txt containing alpha\n
        (repo_dir / "notes.txt").write_text("alpha\n")
        run_git(["add", "notes.txt"], repo_dir, env)
        run_git(["commit", "-m", "Commit A: create notes.txt with alpha"], repo_dir, env)
        commit_a = run_git(["rev-parse", "HEAD"], repo_dir, env)

        # Commit B: append beta\n to notes.txt
        (repo_dir / "notes.txt").write_text("alpha\nbeta\n")
        run_git(["add", "notes.txt"], repo_dir, env)
        run_git(["commit", "-m", "Commit B: append beta to notes.txt"], repo_dir, env)
        commit_b = run_git(["rev-parse", "HEAD"], repo_dir, env)

        # Connect to bare remote using file:// URL
        remote_uri = remote_dir.as_uri()
        run_git(["remote", "add", "origin", remote_uri], repo_dir, env)

        # Push initial main branch through Commit B to remote
        run_git(["push", "-u", "origin", "main"], repo_dir, env)

        # Exercise Step 2: Configure branch.autosetuprebase always locally
        run_git(["config", "branch.autosetuprebase", "always"], repo_dir, env)

        # Exercise Step 3: Create topic tracking origin/main while it points to Commit B
        run_git(["checkout", "-b", "topic", "--track", "origin/main"], repo_dir, env)

        # Verify topic branch tracking & autosetuprebase
        topic_upstream = run_git(["rev-parse", "--abbrev-ref", "topic@{upstream}"], repo_dir, env)
        topic_rebase_cfg = run_git(["config", "--local", "branch.topic.rebase"], repo_dir, env)

        # Exercise Step 5: Switch to main, create Commit C, and push to remote
        run_git(["checkout", "main"], repo_dir, env)
        (repo_dir / "todo.txt").write_text("one\n")
        run_git(["add", "todo.txt"], repo_dir, env)
        run_git(["commit", "-m", "Commit C: create todo.txt with one"], repo_dir, env)
        commit_c = run_git(["rev-parse", "HEAD"], repo_dir, env)
        run_git(["push", "origin", "main"], repo_dir, env)

        # Exercise Step 6 & 7: Switch to topic, create local divergent commit
        run_git(["checkout", "topic"], repo_dir, env)
        (repo_dir / "feature.txt").write_text("feature on topic\n")
        run_git(["add", "feature.txt"], repo_dir, env)
        run_git(["commit", "-m", "Commit D: add feature on topic"], repo_dir, env)
        old_topic_commit = run_git(["rev-parse", "HEAD"], repo_dir, env)
        pre_pull_parent = run_git(["rev-parse", "HEAD^"], repo_dir, env)

        # Exercise Step 8: Configure pull.rebase true locally
        run_git(["config", "pull.rebase", "true"], repo_dir, env)
        pull_rebase_cfg = run_git(["config", "--local", "pull.rebase"], repo_dir, env)

        # Exercise Step 9 & 10: Execute git pull with rebase
        pull_res = subprocess.run(
            ["git", "pull"],
            cwd=repo_dir,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        pull_output = (pull_res.stdout + "\n" + pull_res.stderr).strip()

        # Capture post-pull state dynamically
        new_topic_commit = run_git(["rev-parse", "HEAD"], repo_dir, env)
        post_pull_parent = run_git(["rev-parse", "HEAD^"], repo_dir, env)
        merge_commits = run_git(["rev-list", "--min-parents=2", "HEAD"], repo_dir, env)
        main_ref = run_git(["rev-parse", "refs/heads/main"], repo_dir, env)
        staged_diff = run_git(["diff", "--cached", "--name-only"], repo_dir, env)
        worktree_status = run_git(["status", "--porcelain"], repo_dir, env)

        # Verify file contents
        notes_content = (repo_dir / "notes.txt").read_text()
        todo_content = (repo_dir / "todo.txt").read_text()
        feature_content = (repo_dir / "feature.txt").read_text()

        # Build checks dictionary
        checks = {
            "branch.autosetuprebase is set to always": run_git(["config", "branch.autosetuprebase"], repo_dir, env) == "always",
            "topic branch upstream is configured to origin/main": topic_upstream == "origin/main",
            "branch.topic.rebase was automatically set to true": topic_rebase_cfg == "true",
            "pull.rebase is configured to true": pull_rebase_cfg == "true",
            "pre-pull topic commit had parent Commit B": pre_pull_parent == commit_b,
            "git pull rebased topic onto Commit C (parent is Commit C)": post_pull_parent == commit_c,
            "rebased topic commit hash changed from pre-pull commit": new_topic_commit != old_topic_commit,
            "zero merge commits created (strictly linear history)": merge_commits == "",
            "local main branch remains pointing to Commit C": main_ref == commit_c,
            "index contains no staged changes": staged_diff == "",
            "working tree is clean": worktree_status == "",
            "all expected files exist with correct contents": (
                notes_content == "alpha\nbeta\n"
                and todo_content == "one\n"
                and feature_content == "feature on topic\n"
            ),
        }

        # Save inputs.json
        inputs_data = {
            "task_id": "R11-T040",
            "remote_url": remote_uri,
            "commits": {
                "commit_A": commit_a,
                "commit_B": commit_b,
                "commit_C": commit_c,
                "pre_pull_topic_commit_D": old_topic_commit,
            },
            "commands": [
                "git config branch.autosetuprebase always",
                "git checkout -b topic --track origin/main",
                "git config pull.rebase true",
                "git pull",
            ],
            "configs": {
                "branch.autosetuprebase": "always",
                "branch.topic.rebase": "true",
                "pull.rebase": "true",
            },
        }
        (out_dir / "inputs.json").write_text(json.dumps(inputs_data, indent=2) + "\n")

        # Save expected.json
        expected_data = {
            "topic_upstream": "origin/main",
            "branch_topic_rebase": "true",
            "pull_rebase": "true",
            "post_pull_parent": commit_c,
            "merge_commits_count": 0,
            "main_commit": commit_c,
            "working_tree_clean": True,
            "staged_empty": True,
        }
        (out_dir / "expected.json").write_text(json.dumps(expected_data, indent=2) + "\n")

        # Save results.json
        results_data = {
            "pull_output": pull_output,
            "actual": {
                "commit_A": commit_a,
                "commit_B": commit_b,
                "commit_C": commit_c,
                "old_topic_commit": old_topic_commit,
                "new_topic_commit": new_topic_commit,
                "post_pull_parent": post_pull_parent,
                "merge_commits": merge_commits,
                "main_ref": main_ref,
                "working_tree_clean": worktree_status == "",
                "staged_empty": staged_diff == "",
            },
            "checks": checks,
            "passed": sum(checks.values()),
            "total": len(checks),
        }
        (out_dir / "results.json").write_text(json.dumps(results_data, indent=2) + "\n")

        # Save versions.txt
        git_ver = run_git(["--version"], repo_dir, env)
        py_ver = "Python " + platform.python_version()
        (out_dir / "versions.txt").write_text(f"{git_ver}\n{py_ver}\n")

        # Print check results
        print(f"Running verification for R11-T040 ({len(checks)} checks)...")
        for desc, passed in checks.items():
            status_str = "PASS" if passed else "FAIL"
            print(f"[{status_str}] {desc}")

        all_passed = all(checks.values())
        print(f"\nResult: {sum(checks.values())}/{len(checks)} checks passed.")

        assert all_passed, "One or more assertions failed!"
        print("PASS: All R11-T040 assertions succeeded!")


if __name__ == "__main__":
    main()

