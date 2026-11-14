#!/usr/bin/env python3
"""Demonstrate that git log -S searches history without changing repo state."""

import json
import os
import pathlib
import subprocess
import tempfile


HERE = pathlib.Path(__file__).resolve().parent
AUTHOR_NAME = "Course Student"
AUTHOR_EMAIL = "student@example.invalid"


def run(args, *, cwd, env=None):
    return subprocess.run(
        args, cwd=cwd, env=env, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.strip()


def snapshot(repo):
    refs = run(
        ["git", "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/"],
        cwd=repo,
    ).splitlines()
    tracked_files = run(
        ["git", "ls-files", "--cached", "-z"], cwd=repo
    ).split("\0")
    tracked_files = [name for name in tracked_files if name]
    working_files = {}
    for name in tracked_files:
        path = repo / name
        working_files[name] = path.read_bytes().hex() if path.is_file() else None
    return {
        "head": run(["git", "rev-parse", "HEAD"], cwd=repo),
        "head_ref": run(["git", "symbolic-ref", "-q", "HEAD"], cwd=repo),
        "branch_refs": refs,
        "index_tree": run(["git", "write-tree"], cwd=repo),
        "staged_files": run(["git", "diff", "--cached", "--name-only"], cwd=repo).splitlines(),
        "unstaged_files": run(["git", "diff", "--name-only"], cwd=repo).splitlines(),
        "untracked_files": run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=repo
        ).splitlines(),
        "working_tree_files_hex": working_files,
        "status": run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=repo),
    }


def main():
    inputs = {
        "command": "git log -S'beta' -- notes.txt",
        "author": {"name": AUTHOR_NAME, "email": AUTHOR_EMAIL},
        "commits": {
            "A": "create notes.txt containing alpha\\n",
            "B": "append beta\\n to notes.txt",
            "C": "create todo.txt containing one\\n",
        },
        "branch": "main",
        "topic_points_to": "commit B",
    }
    expected = {
        "result": "Only commit B should be returned because it changes the occurrence count of beta in notes.txt.",
        "state_invariant": "HEAD, branch refs, index, staged/unstaged/untracked files, and tracked working-tree contents are identical before and after the search.",
    }

    with tempfile.TemporaryDirectory(prefix="R11-T052-") as tmp:
        repo = pathlib.Path(tmp) / "repo"
        repo.mkdir()
        env = os.environ.copy()
        env.update({
            "GIT_AUTHOR_NAME": AUTHOR_NAME,
            "GIT_AUTHOR_EMAIL": AUTHOR_EMAIL,
            "GIT_COMMITTER_NAME": AUTHOR_NAME,
            "GIT_COMMITTER_EMAIL": AUTHOR_EMAIL,
        })
        run(["git", "init", "-b", "main"], cwd=repo, env=env)
        run(["git", "config", "user.name", AUTHOR_NAME], cwd=repo, env=env)
        run(["git", "config", "user.email", AUTHOR_EMAIL], cwd=repo, env=env)

        (repo / "notes.txt").write_text("alpha\n", encoding="utf-8")
        run(["git", "add", "notes.txt"], cwd=repo, env=env)
        run(["git", "commit", "-m", "A: add alpha"], cwd=repo, env=env)
        commit_a = run(["git", "rev-parse", "HEAD"], cwd=repo)

        with (repo / "notes.txt").open("a", encoding="utf-8") as notes:
            notes.write("beta\n")
        run(["git", "add", "notes.txt"], cwd=repo, env=env)
        run(["git", "commit", "-m", "B: add beta"], cwd=repo, env=env)
        commit_b = run(["git", "rev-parse", "HEAD"], cwd=repo)

        (repo / "todo.txt").write_text("one\n", encoding="utf-8")
        run(["git", "add", "todo.txt"], cwd=repo, env=env)
        run(["git", "commit", "-m", "C: add todo"], cwd=repo, env=env)
        commit_c = run(["git", "rev-parse", "HEAD"], cwd=repo)
        run(["git", "branch", "topic", commit_b], cwd=repo, env=env)

        before = snapshot(repo)
        output = run(["git", "log", "-Sbeta", "--", "notes.txt"], cwd=repo, env=env)
        found = [line.removeprefix("commit ") for line in output.splitlines() if line.startswith("commit ")]
        after = snapshot(repo)

        # Meaningful checks: identify B only, establish intended branch pointers,
        # and prove the search left all relevant repository state unchanged.
        assert found == [commit_b], f"Expected only B ({commit_b}); got {found}"
        assert before["head"] == commit_c and before["head_ref"] == "refs/heads/main"
        assert f"refs/heads/topic {commit_b}" in before["branch_refs"]
        assert before["status"] == "" and before["staged_files"] == []
        assert before == after, "git log -S changed HEAD, refs, index, or working tree"

        actual = {
            "commit_ids": {"A": commit_a, "B": commit_b, "C": commit_c},
            "search_output_commit_ids": found,
            "search_output": output,
            "before": before,
            "after": after,
            "assertions": {
                "only_commit_b_found": found == [commit_b],
                "main_head_at_c_and_topic_at_b": before["head"] == commit_c and f"refs/heads/topic {commit_b}" in before["branch_refs"],
                "index_clean_before_search": before["status"] == "" and before["staged_files"] == [],
                "repository_state_unchanged": before == after,
            },
        }

    (HERE / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    (HERE / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    (HERE / "actual.json").write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    versions = "\n".join([
        run(["git", "--version"], cwd=HERE),
        run(["python3", "--version"], cwd=HERE),
    ]) + "\n"
    (HERE / "versions.txt").write_text(versions, encoding="utf-8")
    print("PASS: pickaxe found commit B and left repository state unchanged")


if __name__ == "__main__":
    main()
