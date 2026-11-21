#!/usr/bin/env python3
r"""
Verification driver script for task R11-T018:
'Add object notes' guide test and verification

Verifies:
1. Imports and executes tests.guides.test_add_object_notes.
2. Runs both the positive workflow and negative omission failure check in isolated TemporaryDirectory instances.
3. Confirms temporary directories are cleaned up after context exit.
4. Propagates child failures with check=True.
5. Saves inputs, expected vs actual results, and git/python versions into work/R11-T018/results.json.
"""

import os
import sys
import json
import subprocess
import tempfile
import platform

# Add repo root to sys.path to import test module directly
script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from tests.guides.test_add_object_notes import (
    build_scenario_repo,
    run_guide_workflow,
    verify_expected_state,
    NOTE_TEXT
)


def main():
    results_path = os.path.join(script_dir, "results.json")

    git_ver = subprocess.run(
        "git --version", cwd=repo_root, shell=True, capture_output=True, text=True, check=True
    ).stdout.strip()
    py_ver = sys.version.replace("\n", " ")

    # 1. Subprocess invocation of the guide test
    subproc_res = subprocess.run(
        [sys.executable, "tests/guides/test_add_object_notes.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True
    )

    # 2. In-process positive state test in isolated TemporaryDirectory
    pos_temp_dir = None
    pos_scenario = {}
    with tempfile.TemporaryDirectory() as tmpdir_pos:
        pos_temp_dir = tmpdir_pos
        assert os.path.exists(pos_temp_dir), "Positive temp dir does not exist during context"
        pos_scenario = build_scenario_repo(tmpdir_pos)
        run_guide_workflow(tmpdir_pos, execute_decisive_cmd=True)
        pos_verified = verify_expected_state(
            tmpdir_pos,
            pos_scenario["commit_a"],
            pos_scenario["commit_b"],
            pos_scenario["commit_c"],
            pos_scenario["commit_b_tree"],
            pos_scenario["commit_b_parent"]
        )
        assert pos_verified is True, "Positive verify_expected_state failed"

    # Confirm temp dir is cleaned up
    pos_cleaned = not os.path.exists(pos_temp_dir)
    assert pos_cleaned is True, "Positive temp directory was not cleaned up after context exit"

    # 3. In-process negative control check in isolated TemporaryDirectory
    neg_temp_dir = None
    neg_scenario = {}
    neg_raised_assertion = False
    with tempfile.TemporaryDirectory() as tmpdir_neg:
        neg_temp_dir = tmpdir_neg
        assert os.path.exists(neg_temp_dir), "Negative temp dir does not exist during context"
        neg_scenario = build_scenario_repo(tmpdir_neg)
        run_guide_workflow(tmpdir_neg, execute_decisive_cmd=False)
        try:
            verify_expected_state(
                tmpdir_neg,
                neg_scenario["commit_a"],
                neg_scenario["commit_b"],
                neg_scenario["commit_c"],
                neg_scenario["commit_b_tree"],
                neg_scenario["commit_b_parent"]
            )
        except AssertionError:
            neg_raised_assertion = True

    neg_cleaned = not os.path.exists(neg_temp_dir)
    assert neg_raised_assertion is True, "Negative omission check did not raise AssertionError"
    assert neg_cleaned is True, "Negative temp directory was not cleaned up after context exit"

    results_data = {
        "tool_versions": {
            "git": git_ver,
            "python": py_ver,
            "platform": platform.platform()
        },
        "inputs": {
            "test_file": "tests/guides/test_add_object_notes.py",
            "author": "Course Student <student@example.invalid>",
            "initial_branch": "main",
            "commit_a": {"file": "notes.txt", "content": "alpha\n", "message": "Commit A"},
            "commit_b": {"file": "notes.txt", "content_appended": "beta\n", "message": "Commit B"},
            "branch_topic": {"fork_point": "Commit B"},
            "commit_c": {"branch": "main", "file": "todo.txt", "content": "one\n", "message": "Commit C"},
            "decisive_command": f"git notes add -m \"{NOTE_TEXT}\" HEAD~1",
            "note_target": "Commit B (HEAD~1)"
        },
        "expected_results": {
            "subproc_test": "python3 tests/guides/test_add_object_notes.py exits 0 with 2 passing tests",
            "positive_verification": "refs/notes/commits exists, note text matches on Commit B, commits/ancestry unchanged, Commit C has no note",
            "negative_verification": "verify_expected_state raises AssertionError when decisive command is omitted",
            "cleanup": "Temporary directories are automatically removed upon context exit"
        },
        "actual_results": {
            "subproc_exit_code": subproc_res.returncode,
            "subproc_stderr": subproc_res.stderr.strip(),
            "positive_run": {
                "commit_a": pos_scenario["commit_a"],
                "commit_b": pos_scenario["commit_b"],
                "commit_c": pos_scenario["commit_c"],
                "commit_b_tree": pos_scenario["commit_b_tree"],
                "commit_b_parent": pos_scenario["commit_b_parent"],
                "verified": pos_verified,
                "temp_dir_cleaned": pos_cleaned
            },
            "negative_run": {
                "commit_a": neg_scenario["commit_a"],
                "commit_b": neg_scenario["commit_b"],
                "commit_c": neg_scenario["commit_c"],
                "raised_assertion_error": neg_raised_assertion,
                "temp_dir_cleaned": neg_cleaned
            },
            "assertions_passed": True
        }
    }

    os.makedirs(os.path.dirname(results_path), exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)

    print("All checks passed successfully.")
    print(f"Saved results to {results_path}")


if __name__ == "__main__":
    main()
