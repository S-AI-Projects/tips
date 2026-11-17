#!/usr/bin/env python3
"""Demonstrate and correct git stash push -m run outside a repository."""

import json
import os
import pathlib
import subprocess
import tempfile


HERE = pathlib.Path(__file__).resolve().parent
AUTHOR_NAME = "Course Student"
AUTHOR_EMAIL = "student@example.invalid"
MESSAGE = "save point"


def run(args, cwd, env=None, check=True):
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )
    return result


def output(args, cwd, env):
    return run(args, cwd, env).stdout.strip()


def snapshot(repo, env):
    return {
        "head": output(["git", "rev-parse", "HEAD"], repo, env),
        "head_ref": output(["git", "symbolic-ref", "HEAD"], repo, env),
        "branch_refs": output(
            ["git", "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/"],
            repo,
            env,
        ).splitlines(),
        "index_tree": output(["git", "write-tree"], repo, env),
        "staged_files": output(["git", "diff", "--cached", "--name-only"], repo, env).splitlines(),
        "unstaged_files": output(["git", "diff", "--name-only"], repo, env).splitlines(),
        "status": output(["git", "status", "--porcelain=v1", "--untracked-files=all"], repo, env),
        "notes": (repo / "notes.txt").read_text(encoding="utf-8"),
        "todo": (repo / "todo.txt").read_text(encoding="utf-8"),
    }


def make_repository(repo):
    repo.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": AUTHOR_NAME,
            "GIT_AUTHOR_EMAIL": AUTHOR_EMAIL,
            "GIT_COMMITTER_NAME": AUTHOR_NAME,
            "GIT_COMMITTER_EMAIL": AUTHOR_EMAIL,
        }
    )
    run(["git", "init", "-b", "main"], repo, env)
    run(["git", "config", "user.name", AUTHOR_NAME], repo, env)
    run(["git", "config", "user.email", AUTHOR_EMAIL], repo, env)

    (repo / "notes.txt").write_text("alpha\n", encoding="utf-8")
    run(["git", "add", "notes.txt"], repo, env)
    run(["git", "commit", "-m", "A: add alpha"], repo, env)
    commit_a = output(["git", "rev-parse", "HEAD"], repo, env)

    run(["git", "switch", "-c", "topic"], repo, env)
    with (repo / "notes.txt").open("a", encoding="utf-8") as notes:
        notes.write("beta\n")
    run(["git", "add", "notes.txt"], repo, env)
    run(["git", "commit", "-m", "B: add beta"], repo, env)
    commit_b = output(["git", "rev-parse", "HEAD"], repo, env)

    run(["git", "switch", "main"], repo, env)
    (repo / "todo.txt").write_text("one\n", encoding="utf-8")
    run(["git", "add", "todo.txt"], repo, env)
    run(["git", "commit", "-m", "C: add todo"], repo, env)
    commit_c = output(["git", "rev-parse", "HEAD"], repo, env)

    assert output(["git", "rev-parse", "main"], repo, env) == commit_c
    assert output(["git", "rev-parse", "topic"], repo, env) == commit_b
    assert output(["git", "rev-parse", "HEAD^"], repo, env) == commit_a
    assert output(["git", "status", "--porcelain=v1"], repo, env) == ""
    return env, {"A": commit_a, "B": commit_b, "C": commit_c}


def main():
    inputs = {
        "author": {"name": AUTHOR_NAME, "email": AUTHOR_EMAIL},
        "history": {
            "A": "main creates notes.txt containing alpha\\n",
            "B": "topic appends beta\\n to notes.txt",
            "C": "main adds todo.txt containing one\\n",
        },
        "operation": f"git stash push -m {MESSAGE!r}",
        "violated_precondition": "The command is run from the temporary parent directory, outside the Git working tree.",
        "correction": "Run the stash command with cwd set to the repository, while there is a tracked edit to save.",
        "remote": "none; all Git operations use the temporary local repository",
    }
    expected = {
        "bad_case": "Command exits nonzero outside a working tree and leaves the repository state unchanged.",
        "corrected_case": "The same named stash command succeeds in the repository, records the edit, and leaves the working tree clean.",
        "stable_check": "Check the nonzero status and unchanged state rather than matching a full version-specific diagnostic.",
    }

    with tempfile.TemporaryDirectory(prefix="R11-T057-") as temporary:
        root = pathlib.Path(temporary)
        repo = root / "repo"
        env, commits = make_repository(repo)
        before_failure = snapshot(repo, env)

        failed = run(
            ["git", "stash", "push", "-m", MESSAGE],
            root,
            env,
            check=False,
        )
        after_failure = snapshot(repo, env)

        assert failed.returncode != 0, "Running outside a repository must fail."
        assert failed.stderr.strip(), "Git should report why the command could not run."
        assert after_failure == before_failure, "The failed command must leave repository state unchanged."

        with (repo / "notes.txt").open("a", encoding="utf-8") as notes:
            notes.write("temporary edit to save\n")
        before_correction = snapshot(repo, env)
        assert "notes.txt" in before_correction["unstaged_files"]

        corrected = run(["git", "stash", "push", "-m", MESSAGE], repo, env)
        stash_list = output(["git", "stash", "list", "--format=%gd %s"], repo, env).splitlines()
        stash_patch = output(["git", "stash", "show", "-p", "stash@{0}"], repo, env)
        after_correction = snapshot(repo, env)

        assert corrected.returncode == 0
        assert len(stash_list) == 1 and MESSAGE in stash_list[0]
        assert "temporary edit to save" in stash_patch
        assert after_correction["head"] == before_correction["head"]
        assert after_correction["branch_refs"] == before_correction["branch_refs"]
        assert after_correction["status"] == ""
        assert after_correction["notes"] == "alpha\n"

        actual = {
            "commit_ids": commits,
            "bad_case": {
                "command": ["git", "stash", "push", "-m", MESSAGE],
                "working_directory": "temporary parent, outside repository",
                "returncode": failed.returncode,
                "stdout": failed.stdout,
                "stderr": failed.stderr,
                "diagnostic_category": "Git reports that the current directory is not inside a repository; exact wording is intentionally not matched.",
                "state_before": before_failure,
                "state_after": after_failure,
            },
            "corrected_case": {
                "command": ["git", "stash", "push", "-m", MESSAGE],
                "working_directory": "temporary repository root",
                "returncode": corrected.returncode,
                "stash_list": stash_list,
                "stash_patch": stash_patch,
                "state_before": before_correction,
                "state_after": after_correction,
            },
            "assertions": {
                "bad_command_exits_nonzero": failed.returncode != 0,
                "bad_command_leaves_repo_unchanged": after_failure == before_failure,
                "corrected_command_succeeds_and_saves_edit": corrected.returncode == 0 and "temporary edit to save" in stash_patch,
                "corrected_command_preserves_head_and_branch_refs": (
                    after_correction["head"] == before_correction["head"]
                    and after_correction["branch_refs"] == before_correction["branch_refs"]
                ),
                "corrected_command_cleans_worktree": after_correction["status"] == "",
            },
        }

    (HERE / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    (HERE / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    (HERE / "actual.json").write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    versions = "\n".join(
        [
            run(["git", "--version"], HERE).stdout.strip(),
            run(["python3", "--version"], HERE).stdout.strip(),
        ]
    ) + "\n"
    (HERE / "versions.txt").write_text(versions, encoding="utf-8")
    print("PASS: stash command fails outside a repository and succeeds when run inside with changes")


if __name__ == "__main__":
    main()
