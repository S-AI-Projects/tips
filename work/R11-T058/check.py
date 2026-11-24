#!/usr/bin/env python3
"""Check git grep output and prove the search leaves Git state unchanged."""

import json
import os
import pathlib
import subprocess
import sys
import tempfile


HERE = pathlib.Path(__file__).resolve().parent
AUTHOR_NAME = "Course Student"
AUTHOR_EMAIL = "student@example.invalid"
PATTERN = "beta"


def run(args, cwd, env=None, check=True):
    """Run a child process and capture output; checked calls fail immediately."""
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def output(args, cwd, env):
    return run(args, cwd, env).stdout.strip()


def make_search_command(pattern):
    """Build the exact command the guide teaches."""
    return ["git", "grep", "--heading", "--line-number", pattern]


def require_search_command(command):
    """Reject an omitted or altered decisive command before execution."""
    required = ["git", "grep", "--heading", "--line-number"]
    assert command, "The decisive git grep command was omitted."
    assert command[:4] == required, "The decisive command must use git grep --heading --line-number."
    assert len(command) >= 5 and command[4], "The search pattern is missing."


def snapshot(repo, env):
    untracked = output(
        ["git", "ls-files", "--others", "--exclude-standard"], repo, env
    ).splitlines()
    return {
        "head": output(["git", "rev-parse", "HEAD"], repo, env),
        "head_ref": output(["git", "symbolic-ref", "HEAD"], repo, env),
        "branch_refs": output(
            ["git", "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/"],
            repo,
            env,
        ).splitlines(),
        "index_tree": output(["git", "write-tree"], repo, env),
        "staged_files": output(
            ["git", "diff", "--cached", "--name-only"], repo, env
        ).splitlines(),
        "unstaged_files": output(["git", "diff", "--name-only"], repo, env).splitlines(),
        "untracked_files": untracked,
        "status": output(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"], repo, env
        ),
        "notes": (repo / "notes.txt").read_text(encoding="utf-8"),
        "todo": (repo / "todo.txt").read_text(encoding="utf-8")
        if (repo / "todo.txt").exists()
        else None,
        "scratch": (repo / "scratch.txt").read_text(encoding="utf-8"),
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
            # Fixed metadata makes saved evidence stable across checker runs.
            # Commit IDs are still captured dynamically from Git below.
            "GIT_AUTHOR_DATE": "2001-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2001-01-01T00:00:00+00:00",
            "GIT_CONFIG_NOSYSTEM": "1",
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

    run(["git", "switch", "topic"], repo, env)
    # This file matches the pattern but is deliberately untracked.
    (repo / "scratch.txt").write_text("beta\n", encoding="utf-8")

    assert output(["git", "rev-parse", "main"], repo, env) == commit_c
    assert output(["git", "rev-parse", "topic"], repo, env) == commit_b
    assert output(["git", "rev-parse", "HEAD^"], repo, env) == commit_a
    assert output(["git", "status", "--porcelain=v1"], repo, env) == "?? scratch.txt"
    return env, {"A": commit_a, "B": commit_b, "C": commit_c}


def main():
    inputs = {
        "author": {"name": AUTHOR_NAME, "email": AUTHOR_EMAIL},
        "history": {
            "A": "main creates notes.txt containing alpha\\n",
            "B": "topic appends beta\\n to notes.txt",
            "C": "main creates todo.txt containing one\\n",
        },
        "search": "git grep --heading --line-number 'beta'",
        "search_branch": "topic at commit B",
        "untracked_match": "scratch.txt contains beta but is excluded from default tracked-file search",
    }
    expected = {
        "matches": ["notes.txt", "2:beta"],
        "untracked_file_is_not_reported": True,
        "state_unchanged": "HEAD, branch refs, index tree/files, and working-tree state/content are identical before and after the search.",
        "omission_test": "Running the checker with the decisive git grep command omitted exits nonzero before any search runs.",
    }

    with tempfile.TemporaryDirectory(prefix="R11-T058-") as temporary:
        repo = pathlib.Path(temporary) / "repo"
        env, commits = make_repository(repo)
        before = snapshot(repo, env)

        command = None if env.get("R11_T058_OMIT_COMMAND") else make_search_command(PATTERN)
        require_search_command(command)

        # Safe omission test: run this checker in a child with the command removed.
        omission_env = env.copy()
        omission_env["R11_T058_OMIT_COMMAND"] = "1"
        omission_probe = run(
            [sys.executable, str(pathlib.Path(__file__).resolve())],
            repo,
            omission_env,
            check=False,
        )
        assert omission_probe.returncode != 0, "The checker must fail if its decisive command is omitted."
        assert "decisive git grep command was omitted" in omission_probe.stderr

        searched = run(command, repo, env)
        after = snapshot(repo, env)
        lines = searched.stdout.strip().splitlines()

        assert searched.returncode == 0
        assert lines == ["notes.txt", "2:beta"], f"Unexpected git grep output: {lines!r}"
        assert "scratch.txt" not in searched.stdout, "Default git grep must skip untracked files."
        assert before["head"] == commits["B"] and before["head_ref"] == "refs/heads/topic"
        assert before["branch_refs"] == [f"refs/heads/main {commits['C']}", f"refs/heads/topic {commits['B']}"]
        assert before["staged_files"] == [] and before["index_tree"] == after["index_tree"]
        assert before == after, "git grep must not change refs, index, or working-tree state."

        actual = {
            "commit_ids": commits,
            "search_command": command,
            "search_returncode": searched.returncode,
            "search_stdout": searched.stdout,
            "search_stderr": searched.stderr,
            "state_before": before,
            "state_after": after,
            "omission_probe": {
                "command_omitted": True,
                "returncode": omission_probe.returncode,
                "rejected_before_search": "decisive git grep command was omitted" in omission_probe.stderr,
            },
            "assertions": {
                "expected_filename_heading_and_line": lines == ["notes.txt", "2:beta"],
                "untracked_match_is_excluded": "scratch.txt" not in searched.stdout,
                "HEAD_and_branch_refs_unchanged": (
                    before["head"] == after["head"]
                    and before["head_ref"] == after["head_ref"]
                    and before["branch_refs"] == after["branch_refs"]
                ),
                "index_and_worktree_unchanged": before == after,
                "omitted_command_is_rejected": omission_probe.returncode != 0,
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
    print("PASS: git grep output, read-only state, untracked-file exclusion, and omission test")


if __name__ == "__main__":
    main()
