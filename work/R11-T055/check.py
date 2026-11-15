#!/usr/bin/env python3
"""Check author filtering and path quoting for a path with spaces."""

import json
import os
import pathlib
import subprocess
import tempfile


HERE = pathlib.Path(__file__).resolve().parent
AUTHOR_NAME = "Course Student"
AUTHOR_EMAIL = "student@example.invalid"
SPACED_PATH = "sample data/release notes.txt"


def run(args, *, cwd, env=None):
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def snapshot(repo):
    return {
        "head": run(["git", "rev-parse", "HEAD"], cwd=repo),
        "head_ref": run(["git", "symbolic-ref", "-q", "HEAD"], cwd=repo),
        "branch_refs": run(
            ["git", "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/"],
            cwd=repo,
        ).splitlines(),
        "tree": run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo),
        "index_tree": run(["git", "write-tree"], cwd=repo),
        "staged_files": run(["git", "diff", "--cached", "--name-only"], cwd=repo).splitlines(),
        "unstaged_files": run(["git", "diff", "--name-only"], cwd=repo).splitlines(),
        "untracked_files": run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=repo
        ).splitlines(),
        "files": {
            name: (repo / name).read_text(encoding="utf-8")
            for name in ("notes.txt", "todo.txt", SPACED_PATH)
        },
        "status": run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=repo),
    }


def main():
    excluded_author_command = [
        "git", "log", "--perl-regexp", "--author=^((?!Course Student).*)$",
        "--", SPACED_PATH,
    ]
    path_check_command = ["git", "log", "--format=%s", "--", SPACED_PATH]
    inputs = {
        "author": {"name": AUTHOR_NAME, "email": AUTHOR_EMAIL},
        "commits": {
            "A": "create notes.txt with alpha\\n and sample data/release notes.txt",
            "B": "append beta\\n to notes.txt on topic",
            "C": "create todo.txt with one\\n on main",
        },
        "branches": {"main": "commit C", "topic": "commit B"},
        "spaced_path": SPACED_PATH,
        "excluded_author_command": "git log --perl-regexp --author='^((?!Course Student).*)$' -- 'sample data/release notes.txt'",
        "path_check_command": "git log --format=%s -- 'sample data/release notes.txt'",
    }
    expected = {
        "unfiltered_path_subjects": ["A: add release notes"],
        "excluded_author_output": "",
        "head_after_search": "HEAD stays on main at commit C",
        "topic_ref": "stays at commit B",
        "search_side_effects": "HEAD, refs, index, and working-tree files are unchanged.",
    }

    with tempfile.TemporaryDirectory(prefix="R11-T055-") as tmp:
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
        spaced_file = repo / SPACED_PATH
        spaced_file.parent.mkdir(parents=True)
        spaced_file.write_text("release notes\n", encoding="utf-8")
        run(["git", "add", "notes.txt", SPACED_PATH], cwd=repo, env=env)
        run(["git", "commit", "-m", "A: add release notes"], cwd=repo, env=env)
        commit_a = run(["git", "rev-parse", "HEAD"], cwd=repo)

        run(["git", "switch", "-c", "topic"], cwd=repo, env=env)
        with (repo / "notes.txt").open("a", encoding="utf-8") as notes:
            notes.write("beta\n")
        run(["git", "add", "notes.txt"], cwd=repo, env=env)
        run(["git", "commit", "-m", "B: add beta"], cwd=repo, env=env)
        commit_b = run(["git", "rev-parse", "HEAD"], cwd=repo)

        run(["git", "switch", "main"], cwd=repo, env=env)
        (repo / "todo.txt").write_text("one\n", encoding="utf-8")
        run(["git", "add", "todo.txt"], cwd=repo, env=env)
        run(["git", "commit", "-m", "C: add todo"], cwd=repo, env=env)
        commit_c = run(["git", "rev-parse", "HEAD"], cwd=repo)

        before_search = snapshot(repo)
        unfiltered_subjects = run(path_check_command, cwd=repo, env=env).splitlines()
        excluded_author_output = run(excluded_author_command, cwd=repo, env=env)
        after_search = snapshot(repo)

        assert unfiltered_subjects == ["A: add release notes"]
        assert excluded_author_output == ""
        assert before_search["head"] == after_search["head"] == commit_c
        assert before_search["head_ref"] == after_search["head_ref"] == "refs/heads/main"
        assert f"refs/heads/topic {commit_b}" in before_search["branch_refs"]
        assert after_search["branch_refs"] == before_search["branch_refs"]
        assert after_search["tree"] == before_search["tree"]
        assert after_search["index_tree"] == before_search["index_tree"]
        assert after_search["files"] == before_search["files"]
        assert after_search["status"] == before_search["status"] == ""
        assert after_search["staged_files"] == after_search["unstaged_files"] == []
        assert after_search["untracked_files"] == []
        assert not run(["git", "remote", "-v"], cwd=repo)

        actual = {
            "commit_ids": {"A": commit_a, "B": commit_b, "C": commit_c},
            "before_search": before_search,
            "unfiltered_path_subjects": unfiltered_subjects,
            "excluded_author_output": excluded_author_output,
            "after_search": after_search,
            "assertions": {
                "quoted_spaced_path_finds_only_commit_a": unfiltered_subjects == ["A: add release notes"],
                "course_student_author_is_excluded": excluded_author_output == "",
                "main_head_and_topic_ref_are_expected": (
                    after_search["head"] == commit_c
                    and after_search["head_ref"] == "refs/heads/main"
                    and f"refs/heads/topic {commit_b}" in after_search["branch_refs"]
                ),
                "log_search_leaves_refs_index_and_files_unchanged": (
                    after_search["head"] == before_search["head"]
                    and after_search["branch_refs"] == before_search["branch_refs"]
                    and after_search["index_tree"] == before_search["index_tree"]
                    and after_search["files"] == before_search["files"]
                ),
                "working_tree_is_clean_after_search": after_search["status"] == "",
                "no_remote_was_needed": not run(["git", "remote", "-v"], cwd=repo),
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
    print("PASS: the quoted spaced path is matched and the author filter excludes the fixture author")


if __name__ == "__main__":
    main()
