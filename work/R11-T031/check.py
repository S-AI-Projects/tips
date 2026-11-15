#!/usr/bin/env python3
"""
Verification script for GitHub Issue #4 (R11-T031).
Verifies the reproducible git clean -fd --dry-run example:
1. Repository initialized with branch 'main'.
2. Author set to 'Course Student <student@example.invalid>'.
3. Commit A: notes.txt containing 'alpha'.
4. Commit B: append 'beta' to notes.txt.
5. Create branch 'topic' at Commit B.
6. Commit C: todo.txt containing 'one'.
7. Untracked file (scratch.txt) and untracked directory (untracked_dir/) added.
8. git clean -fd --dry-run demonstrates dry-run output without deleting files.
9. Assertions verifying meaningful Git state facts.
"""

import os
import subprocess
import tempfile
import sys


def run_cmd(cmd, cwd, env=None):
    """Run command and return stdout, asserting return code is 0."""
    res = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=True
    )
    return res.stdout


def verify_setup(base_dir=None):
    """Execute complete reproducible setup and assert meaningful Git facts."""
    with tempfile.TemporaryDirectory(dir=base_dir) as td:
        repo_dir = td

        # Environment to guarantee reproducible commit author/committer
        env = os.environ.copy()
        env["GIT_AUTHOR_NAME"] = "Course Student"
        env["GIT_AUTHOR_EMAIL"] = "student@example.invalid"
        env["GIT_COMMITTER_NAME"] = "Course Student"
        env["GIT_COMMITTER_EMAIL"] = "student@example.invalid"

        # 1. Initialize repo with branch 'main'
        run_cmd(["git", "init", "-b", "main"], cwd=repo_dir, env=env)
        run_cmd(["git", "config", "user.name", "Course Student"], cwd=repo_dir, env=env)
        run_cmd(["git", "config", "user.email", "student@example.invalid"], cwd=repo_dir, env=env)

        # 2. Commit A: notes.txt containing 'alpha'
        notes_file = os.path.join(repo_dir, "notes.txt")
        with open(notes_file, "w") as f:
            f.write("alpha\n")
        run_cmd(["git", "add", "notes.txt"], cwd=repo_dir, env=env)
        run_cmd(["git", "commit", "-m", "Commit A: notes.txt with alpha"], cwd=repo_dir, env=env)

        # 3. Commit B: append 'beta' to notes.txt
        with open(notes_file, "a") as f:
            f.write("beta\n")
        run_cmd(["git", "add", "notes.txt"], cwd=repo_dir, env=env)
        run_cmd(["git", "commit", "-m", "Commit B: append beta"], cwd=repo_dir, env=env)

        commit_b_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).strip()

        # 4. Create branch 'topic' at commit B
        run_cmd(["git", "branch", "topic"], cwd=repo_dir, env=env)

        # 5. Commit C: todo.txt containing 'one'
        todo_file = os.path.join(repo_dir, "todo.txt")
        with open(todo_file, "w") as f:
            f.write("one\n")
        run_cmd(["git", "add", "todo.txt"], cwd=repo_dir, env=env)
        run_cmd(["git", "commit", "-m", "Commit C: todo.txt with one"], cwd=repo_dir, env=env)

        commit_c_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).strip()

        # 6. Add untracked files and directories
        scratch_file = os.path.join(repo_dir, "scratch.txt")
        with open(scratch_file, "w") as f:
            f.write("temporary notes\n")

        untracked_dir = os.path.join(repo_dir, "untracked_dir")
        os.makedirs(untracked_dir, exist_ok=True)
        untracked_log = os.path.join(untracked_dir, "temp.log")
        with open(untracked_log, "w") as f:
            f.write("log data\n")

        # 7. Execute git clean -fd --dry-run
        dry_run_output = run_cmd(["git", "clean", "-fd", "--dry-run"], cwd=repo_dir, env=env)

        # ---------------------------------------------------------
        # ASSERTIONS: Verify meaningful Git state facts
        # ---------------------------------------------------------

        # Fact 1: Current branch is 'main'
        current_branch = run_cmd(["git", "branch", "--show-current"], cwd=repo_dir, env=env).strip()
        assert current_branch == "main", (
            f"Assertion Failed: expected current branch 'main', got '{current_branch}'"
        )

        # Fact 2: Author of all commits is 'Course Student <student@example.invalid>'
        authors = run_cmd(
            ["git", "log", "--format=%an <%ae>"], cwd=repo_dir, env=env
        ).strip().splitlines()
        assert len(authors) == 3, f"Assertion Failed: expected 3 commits on main, got {len(authors)}"
        for author in authors:
            assert author == "Course Student <student@example.invalid>", (
                f"Assertion Failed: expected author 'Course Student <student@example.invalid>', got '{author}'"
            )

        # Fact 3: Branch 'topic' points to Commit B
        topic_hash = run_cmd(["git", "rev-parse", "topic"], cwd=repo_dir, env=env).strip()
        assert topic_hash == commit_b_hash, (
            f"Assertion Failed: topic branch points to {topic_hash}, expected Commit B ({commit_b_hash})"
        )

        # Fact 4: Commit contents:
        # Commit A has notes.txt with 'alpha\n'
        content_commit_a = run_cmd(["git", "show", "main~2:notes.txt"], cwd=repo_dir, env=env)
        assert content_commit_a == "alpha\n", (
            f"Assertion Failed: expected 'alpha\\n' in Commit A, got {content_commit_a!r}"
        )
        # Commit B has notes.txt with 'alpha\nbeta\n'
        content_commit_b = run_cmd(["git", "show", "main~1:notes.txt"], cwd=repo_dir, env=env)
        assert content_commit_b == "alpha\nbeta\n", (
            f"Assertion Failed: expected 'alpha\\nbeta\\n' in Commit B, got {content_commit_b!r}"
        )
        # Commit C has todo.txt with 'one\n'
        content_commit_c = run_cmd(["git", "show", "main:todo.txt"], cwd=repo_dir, env=env)
        assert content_commit_c == "one\n", (
            f"Assertion Failed: expected 'one\\n' in Commit C, got {content_commit_c!r}"
        )

        # Fact 5: git clean -fd --dry-run output includes both untracked file and untracked dir
        assert "Would remove scratch.txt" in dry_run_output, (
            f"Assertion Failed: 'Would remove scratch.txt' not found in dry-run output:\n{dry_run_output}"
        )
        assert (
            "Would remove untracked_dir/" in dry_run_output or "Would remove untracked_dir" in dry_run_output
        ), (
            f"Assertion Failed: 'Would remove untracked_dir/' not found in dry-run output:\n{dry_run_output}"
        )

        # Fact 6: Crucial safety check: nothing was deleted!
        assert os.path.isfile(scratch_file), "Assertion Failed: scratch.txt was deleted during dry run!"
        assert os.path.isdir(untracked_dir), "Assertion Failed: untracked_dir was deleted during dry run!"
        assert os.path.isfile(untracked_log), "Assertion Failed: untracked_dir/temp.log was deleted during dry run!"

        # Fact 7: git status confirms files remain untracked
        status_output = run_cmd(["git", "status", "--porcelain"], cwd=repo_dir, env=env)
        assert "?? scratch.txt" in status_output, (
            f"Assertion Failed: scratch.txt not marked untracked in status:\n{status_output}"
        )
        assert "?? untracked_dir/" in status_output, (
            f"Assertion Failed: untracked_dir/ not marked untracked in status:\n{status_output}"
        )

        # Capture actual output summary for reporting
        log_graph = run_cmd(
            ["git", "log", "--all", "--graph", "--oneline", "--decorate"],
            cwd=repo_dir,
            env=env
        )

        return {
            "dry_run_output": dry_run_output,
            "status_output": status_output,
            "log_graph": log_graph,
            "commit_b_hash": commit_b_hash,
            "commit_c_hash": commit_c_hash,
            "topic_hash": topic_hash,
        }


def main():
    print("Running verification test for Issue #4 (R11-T031)...")
    result = verify_setup()
    print("All assertions passed successfully!")
    print("\n[git clean -fd --dry-run output]:")
    print(result["dry_run_output"].strip())
    print("\n[git status --porcelain]:")
    print(result["status_output"].strip())
    print("\n[git log --all --graph --oneline --decorate]:")
    print(result["log_graph"].strip())


if __name__ == "__main__":
    main()
