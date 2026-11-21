#!/usr/bin/env python3
r"""
Integration and guide test for 'Add object notes' (git notes add -m 'Note on the previous commit....').

Verifies:
1. Temporary repository setup:
   - Branch 'main'
   - Author: 'Course Student <student@example.invalid>'
   - Commit A (notes.txt = "alpha\n")
   - Commit B (notes.txt appended with "beta\n")
   - Branch 'topic' at Commit B
   - Commit C (todo.txt = "one\n")
2. Helper functions:
   - run_guide_workflow(repo, execute_decisive_cmd=True)
   - verify_expected_state(repo, commit_a, commit_b, commit_c, commit_b_tree, commit_b_parent)
3. Assertions in verify_expected_state:
   - refs/notes/commits exists and git notes show <commit_b> outputs 'Note on the previous commit....'
   - Adding a note does NOT alter commit SHAs or ancestry (HEAD == commit_c, HEAD~1 == commit_b, HEAD~2 == commit_a, topic == commit_b, and commit_b tree/parent hashes unchanged)
   - Commit C (HEAD) has no note (git notes show <commit_c> exits non-zero)
4. Negative control:
   - Proves that omitting the decisive command (execute_decisive_cmd=False) causes verify_expected_state to raise AssertionError
"""

import os
import sys
import unittest
import tempfile
import subprocess


NOTE_TEXT = "Note on the previous commit...."


def run_cmd(cmd: str, cwd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Runs a shell command in cwd via subprocess."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        check=check
    )


def build_scenario_repo(repo_dir: str) -> dict:
    """Initializes the baseline repository scenario with Commits A, B, topic branch, and Commit C."""
    run_cmd("git init -b main", repo_dir, check=True)
    run_cmd("git config user.name \"Course Student\"", repo_dir, check=True)
    run_cmd("git config user.email \"student@example.invalid\"", repo_dir, check=True)

    # Commit A
    notes_file = os.path.join(repo_dir, "notes.txt")
    with open(notes_file, "w", encoding="utf-8") as f:
        f.write("alpha\n")
    run_cmd("git add notes.txt", repo_dir, check=True)
    run_cmd("git commit -m \"Commit A\"", repo_dir, check=True)
    commit_a = run_cmd("git rev-parse HEAD", repo_dir, check=True).stdout.strip()

    # Commit B
    with open(notes_file, "a", encoding="utf-8") as f:
        f.write("beta\n")
    run_cmd("git add notes.txt", repo_dir, check=True)
    run_cmd("git commit -m \"Commit B\"", repo_dir, check=True)
    commit_b = run_cmd("git rev-parse HEAD", repo_dir, check=True).stdout.strip()
    commit_b_tree = run_cmd(f"git rev-parse {commit_b}^{{tree}}", repo_dir, check=True).stdout.strip()
    commit_b_parent = run_cmd(f"git rev-parse {commit_b}^", repo_dir, check=True).stdout.strip()

    # Branch topic at B
    run_cmd("git branch topic", repo_dir, check=True)

    # Commit C on main
    todo_file = os.path.join(repo_dir, "todo.txt")
    with open(todo_file, "w", encoding="utf-8") as f:
        f.write("one\n")
    run_cmd("git add todo.txt", repo_dir, check=True)
    run_cmd("git commit -m \"Commit C\"", repo_dir, check=True)
    commit_c = run_cmd("git rev-parse HEAD", repo_dir, check=True).stdout.strip()

    return {
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "commit_b_tree": commit_b_tree,
        "commit_b_parent": commit_b_parent
    }


def run_guide_workflow(repo: str, execute_decisive_cmd: bool = True) -> subprocess.CompletedProcess:
    """Runs git notes add on Commit B (HEAD~1) when execute_decisive_cmd=True, otherwise skips it."""
    if execute_decisive_cmd:
        cmd = f"git notes add -m \"{NOTE_TEXT}\" HEAD~1"
        return run_cmd(cmd, repo, check=True)
    return None


def verify_expected_state(repo: str, commit_a: str, commit_b: str, commit_c: str,
                          commit_b_tree: str = None, commit_b_parent: str = None) -> bool:
    """
    Asserts expected state:
    1. refs/notes/commits exists and git notes show <commit_b> outputs NOTE_TEXT.
    2. Commit SHAs and ancestry are completely unaltered.
    3. Commit C has no note (git notes show <commit_c> fails non-zero).
    """
    # 1. Verify refs/notes/commits and note content on Commit B
    ref_check = run_cmd("git rev-parse refs/notes/commits", repo, check=False)
    if ref_check.returncode != 0:
        raise AssertionError("refs/notes/commits ref does not exist")

    show_b = run_cmd(f"git notes show {commit_b}", repo, check=False)
    if show_b.returncode != 0:
        raise AssertionError(f"git notes show {commit_b} failed non-zero: {show_b.stderr}")
    if show_b.stdout.strip() != NOTE_TEXT:
        raise AssertionError(f"Note content '{show_b.stdout.strip()}' != '{NOTE_TEXT}'")

    # 2. Verify commit SHAs, ancestry, and tree/parent immutability
    head_sha = run_cmd("git rev-parse HEAD", repo, check=True).stdout.strip()
    head1_sha = run_cmd("git rev-parse HEAD~1", repo, check=True).stdout.strip()
    head2_sha = run_cmd("git rev-parse HEAD~2", repo, check=True).stdout.strip()
    topic_sha = run_cmd("git rev-parse topic", repo, check=True).stdout.strip()

    if head_sha != commit_c:
        raise AssertionError(f"HEAD altered: {head_sha} != {commit_c}")
    if head1_sha != commit_b:
        raise AssertionError(f"HEAD~1 altered: {head1_sha} != {commit_b}")
    if head2_sha != commit_a:
        raise AssertionError(f"HEAD~2 altered: {head2_sha} != {commit_a}")
    if topic_sha != commit_b:
        raise AssertionError(f"topic ref altered: {topic_sha} != {commit_b}")

    if commit_b_tree:
        curr_b_tree = run_cmd(f"git rev-parse {commit_b}^{{tree}}", repo, check=True).stdout.strip()
        if curr_b_tree != commit_b_tree:
            raise AssertionError(f"Commit B tree altered: {curr_b_tree} != {commit_b_tree}")
    if commit_b_parent:
        curr_b_parent = run_cmd(f"git rev-parse {commit_b}^", repo, check=True).stdout.strip()
        if curr_b_parent != commit_b_parent:
            raise AssertionError(f"Commit B parent altered: {curr_b_parent} != {commit_b_parent}")

    # 3. Verify Commit C has no note
    show_c = run_cmd(f"git notes show {commit_c}", repo, check=False)
    if show_c.returncode == 0:
        raise AssertionError(f"Commit C unexpectedly has a note attached: {show_c.stdout}")

    return True


class TestAddObjectNotes(unittest.TestCase):
    """Unit and integration test cases for git notes guide."""

    def test_positive_workflow(self):
        """Positive test: decisive command executed, assertions pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scenario = build_scenario_repo(tmpdir)
            run_guide_workflow(tmpdir, execute_decisive_cmd=True)
            verified = verify_expected_state(
                tmpdir,
                scenario["commit_a"],
                scenario["commit_b"],
                scenario["commit_c"],
                scenario["commit_b_tree"],
                scenario["commit_b_parent"]
            )
            self.assertTrue(verified)

    def test_negative_omission_workflow(self):
        """Negative control: decisive command omitted, verify_expected_state raises AssertionError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scenario = build_scenario_repo(tmpdir)
            run_guide_workflow(tmpdir, execute_decisive_cmd=False)
            with self.assertRaises(AssertionError):
                verify_expected_state(
                    tmpdir,
                    scenario["commit_a"],
                    scenario["commit_b"],
                    scenario["commit_c"],
                    scenario["commit_b_tree"],
                    scenario["commit_b_parent"]
                )


if __name__ == "__main__":
    unittest.main()
