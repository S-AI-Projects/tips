#!/usr/bin/env python3
"""Reproduce and verify the local Git subtree example in isolated repositories."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ARTIFACTS = Path(__file__).resolve().parent
IDENTITY = {"GIT_AUTHOR_NAME": "Course Student", "GIT_AUTHOR_EMAIL": "student@example.invalid",
            "GIT_COMMITTER_NAME": "Course Student", "GIT_COMMITTER_EMAIL": "student@example.invalid",
            "GIT_AUTHOR_DATE": "2020-01-01T00:00:00+0000",
            "GIT_COMMITTER_DATE": "2020-01-01T00:00:00+0000"}
INPUTS = {
    "initial_branch": "main",
    "author": "Course Student <student@example.invalid>",
    "commit_A": {"message": "A", "files": {"notes.txt": "alpha\n"}},
    "commit_B": {"message": "B", "append": {"notes.txt": "beta\n"}},
    "topic_branch": "topic",
    "topic_created_at": "B",
    "commit_C": {"message": "C", "files": {"todo.txt": "one\n"}},
    "subtree_prefix": "vendor/project",
    "remote": "second local bare repository, addressed by file:// URL",
    "repeatability": "two independent temporary directory trees; fixed commit timestamps",
}
EXPECTED = {
    "authors": {"main": "Course Student <student@example.invalid>",
                "main^": "Course Student <student@example.invalid>",
                "main^^": "Course Student <student@example.invalid>"},
    "source_main_messages": ["C", "B", "A"],
    "source_topic_messages": ["B", "A"],
    "topic_ref_equals_commit_B": True,
    "commit_C_parent_equals_commit_B": True,
    "source_files": {"notes.txt": "alpha\nbeta\n", "todo.txt": "one\n"},
    "subtree_prefix": "vendor/project",
    "host_subtree_files": {"vendor/project/notes.txt": "alpha\nbeta\n",
                            "vendor/project/todo.txt": "one\n"},
    "host_worktree_clean_after_add": True,
    "two_runs_have_same_git_object_ids": True,
}


def run(args, cwd=None, env=None):
    merged = os.environ.copy()
    merged.update(IDENTITY)
    if env:
        merged.update(env)
    return subprocess.run(args, cwd=cwd, env=merged, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def git(repo, *args, env=None):
    return run(["git", *args], cwd=repo, env=env).stdout.strip()


def commit(repo, message):
    git(repo, "add", "--all")
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def reproduce(parent):
    source = parent / "project"
    bare = parent / "project.git"
    host = parent / "host"
    run(["git", "init", "--bare", "--initial-branch=main", str(bare)])
    run(["git", "init", "--initial-branch=main", str(source)])
    (source / "notes.txt").write_text("alpha\n")
    commit(source, "A")
    id_a = git(source, "rev-parse", "HEAD")
    with (source / "notes.txt").open("a") as f:
        f.write("beta\n")
    commit(source, "B")
    id_b = git(source, "rev-parse", "HEAD")
    git(source, "branch", "topic")
    git(source, "checkout", "main")
    (source / "todo.txt").write_text("one\n")
    commit(source, "C")
    id_c = git(source, "rev-parse", "HEAD")
    git(source, "remote", "add", "origin", bare.as_uri())
    git(source, "push", "--all", "origin")

    run(["git", "init", "--initial-branch=main", str(host)])
    (host / "README.md").write_text("Host project\n")
    commit(host, "Host project")
    git(host, "remote", "add", "origin", bare.as_uri())
    git(host, "subtree", "add", "--prefix=vendor/project", "--squash", "origin", "main")

    authors = {name: git(source, "show", "-s", "--format=%an <%ae>", name)
               for name in ("main", "main^", "main^^")}
    assert set(authors.values()) == {"Course Student <student@example.invalid>"}, authors
    main_messages = git(source, "log", "--format=%s", "main").splitlines()
    topic_messages = git(source, "log", "--format=%s", "topic").splitlines()
    assert main_messages == ["C", "B", "A"], main_messages
    assert topic_messages == ["B", "A"], topic_messages
    assert git(source, "rev-parse", "topic") == id_b
    assert git(source, "rev-parse", "main^") == id_b
    assert git(source, "rev-parse", "main") == id_c
    files = {name: (source / name).read_text() for name in ("notes.txt", "todo.txt")}
    assert files == {"notes.txt": "alpha\nbeta\n", "todo.txt": "one\n"}, files
    subtree_files = {
        "vendor/project/notes.txt": run(["git", "show", "HEAD:vendor/project/notes.txt"], cwd=host).stdout,
        "vendor/project/todo.txt": run(["git", "show", "HEAD:vendor/project/todo.txt"], cwd=host).stdout,
    }
    assert subtree_files == EXPECTED["host_subtree_files"], subtree_files
    status = git(host, "status", "--porcelain")
    assert status == "", f"host worktree is not clean: {status}"
    return {
        "commit_ids": {"A": id_a, "B": id_b, "C": id_c,
                       "topic": git(source, "rev-parse", "topic"),
                       "subtree_add": git(host, "rev-parse", "HEAD")},
        "authors": authors,
        "source_main_messages": main_messages,
        "source_topic_messages": topic_messages,
        "topic_ref_equals_commit_B": git(source, "rev-parse", "topic") == id_b,
        "commit_C_parent_equals_commit_B": git(source, "rev-parse", "main^") == id_b,
        "source_files": files,
        "host_subtree_files": subtree_files,
        "host_worktree_clean_after_add": status == "",
        "host_subtree_add_subject": git(host, "log", "-1", "--format=%s"),
    }


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "inputs.json").write_text(json.dumps(INPUTS, indent=2) + "\n")
    (ARTIFACTS / "expected.json").write_text(json.dumps(EXPECTED, indent=2) + "\n")
    outcomes = []
    for _ in range(2):
        with tempfile.TemporaryDirectory(prefix="r11-t051-") as tmp:
            outcomes.append(reproduce(Path(tmp)))
    assert outcomes[0]["commit_ids"] == outcomes[1]["commit_ids"], outcomes
    for actual in outcomes:
        for key in ("source_main_messages", "source_topic_messages", "topic_ref_equals_commit_B",
                    "commit_C_parent_equals_commit_B", "source_files", "host_subtree_files", "authors",
                    "host_worktree_clean_after_add"):
            assert actual[key] == EXPECTED[key], (key, actual[key], EXPECTED[key])
    result = {"runs": outcomes, "same_object_ids_across_separate_temp_dirs": True}
    (ARTIFACTS / "actual.json").write_text(json.dumps(result, indent=2) + "\n")
    versions = {}
    for label, command in (("git", ["git", "--version"]),
                           ("node", ["node", "--version"]),
                           ("npm", ["npm", "--version"]),
                           ("python", ["python3", "--version"])):
        executable = shutil.which(command[0])
        if executable:
            result = run(command)
            versions[label] = result.stdout.strip() or result.stderr.strip()
        else:
            versions[label] = "unavailable (executable not found on PATH)"
    versions["git_subtree"] = shutil.which("git-subtree") or "available via `git subtree` (verified by both runs)"
    (ARTIFACTS / "versions.txt").write_text("\n".join(f"{k}: {v}" for k, v in versions.items()) + "\n")
    print("R11-T051 subtree reproduction passed in two separate temporary directories.")
    print(f"Captured object IDs: {json.dumps(outcomes[0]['commit_ids'], sort_keys=True)}")
    print(f"Results saved in {ARTIFACTS}")


if __name__ == "__main__":
    main()
