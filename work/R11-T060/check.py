#!/usr/bin/env python3
"""Check which ref `git push origin :refs/tags/<tag>` deletes."""

import json
import os
import pathlib
import subprocess
import tempfile


HERE = pathlib.Path(__file__).resolve().parent
AUTHOR_NAME = "Course Student"
AUTHOR_EMAIL = "student@example.invalid"
TAG = "demo-v1"
FIXED_DATE = "2001-01-01T00:00:00+00:00"


def run(args, cwd, env=None, check=True):
    """Run a subprocess; checked command failures raise CalledProcessError."""
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


def bare_output(remote, args, cwd, env):
    return output(["git", f"--git-dir={remote}", *args], cwd, env)


def refs(repo, env, namespace):
    return output(
        ["git", "for-each-ref", "--format=%(refname) %(objectname)", namespace],
        repo,
        env,
    ).splitlines()


def bare_refs(remote, cwd, env, namespace):
    return bare_output(
        remote,
        ["for-each-ref", "--format=%(refname) %(objectname)", namespace],
        cwd,
        env,
    ).splitlines()


def local_snapshot(repo, env):
    return {
        "head": output(["git", "rev-parse", "HEAD"], repo, env),
        "head_ref": output(["git", "symbolic-ref", "HEAD"], repo, env),
        "branch_refs": refs(repo, env, "refs/heads/"),
        "tag_refs": refs(repo, env, "refs/tags/"),
        "index_tree": output(["git", "write-tree"], repo, env),
        "staged_files": output(
            ["git", "diff", "--cached", "--name-only"], repo, env
        ).splitlines(),
        "unstaged_files": output(["git", "diff", "--name-only"], repo, env).splitlines(),
        "status": output(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"], repo, env
        ),
        "notes": (repo / "notes.txt").read_text(encoding="utf-8"),
        "todo": (repo / "todo.txt").read_text(encoding="utf-8"),
    }


def make_fixture(repo, remote):
    repo.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": AUTHOR_NAME,
            "GIT_AUTHOR_EMAIL": AUTHOR_EMAIL,
            "GIT_COMMITTER_NAME": AUTHOR_NAME,
            "GIT_COMMITTER_EMAIL": AUTHOR_EMAIL,
            "GIT_AUTHOR_DATE": FIXED_DATE,
            "GIT_COMMITTER_DATE": FIXED_DATE,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        }
    )

    run(["git", "init", "--bare", "--initial-branch=main", str(remote)], repo.parent, env)
    run(["git", "init", "-b", "main"], repo, env)
    run(["git", "config", "--local", "user.name", AUTHOR_NAME], repo, env)
    run(["git", "config", "--local", "user.email", AUTHOR_EMAIL], repo, env)

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

    run(["git", "remote", "add", "origin", remote.as_uri()], repo, env)
    run(["git", "push", "origin", "main", "topic"], repo, env)
    run(["git", "tag", TAG, "topic"], repo, env)
    run(["git", "push", "origin", f"refs/tags/{TAG}"], repo, env)

    assert output(["git", "rev-parse", "--show-toplevel"], repo, env) == str(repo.resolve())
    assert output(["git", "branch", "--show-current"], repo, env) == "main"
    assert output(["git", "rev-parse", "main"], repo, env) == commit_c
    assert output(["git", "rev-parse", "topic"], repo, env) == commit_b
    assert output(["git", "rev-parse", "HEAD^"], repo, env) == commit_a
    assert output(["git", "rev-parse", f"refs/tags/{TAG}"], repo, env) == commit_b
    assert output(["git", "config", "--local", "--get", "user.name"], repo, env) == AUTHOR_NAME
    assert output(["git", "config", "--local", "--get", "user.email"], repo, env) == AUTHOR_EMAIL
    assert output(["git", "status", "--porcelain=v1"], repo, env) == ""
    assert bare_refs(remote, repo, env, "refs/tags/") == [f"refs/tags/{TAG} {commit_b}"]
    return env, {"A": commit_a, "B": commit_b, "C": commit_c}


def main():
    inputs = {
        "author": {"name": AUTHOR_NAME, "email": AUTHOR_EMAIL},
        "history": {
            "A": "main creates notes.txt containing alpha\\n",
            "B": "topic appends beta\\n to notes.txt",
            "C": "main creates todo.txt containing one\\n",
        },
        "tag": TAG,
        "tag_target": "topic at commit B",
        "current_branch": "main at commit C",
        "remote": "second local bare repository configured as origin using file:// URL",
        "operation": ["git", "push", "origin", f":refs/tags/{TAG}"],
        "prediction": "Only remote refs/tags/demo-v1 is removed. Local tag, branches, HEAD, index, and working tree stay unchanged.",
    }
    expected = {
        "remote_tag_ref_deleted": True,
        "local_tag_still_points_to_B": True,
        "local_branches_head_index_worktree_unchanged": True,
        "remote_branch_refs_unchanged": True,
        "commit_B_remains_reachable_from_remote_topic": True,
    }

    with tempfile.TemporaryDirectory(prefix="R11-T060-") as temporary:
        root = pathlib.Path(temporary)
        repo = root / "repo"
        remote = root / "remote.git"
        env, commits = make_fixture(repo, remote)

        before_local = local_snapshot(repo, env)
        before_remote_branches = bare_refs(remote, repo, env, "refs/heads/")
        before_remote_tags = bare_refs(remote, repo, env, "refs/tags/")
        deletion = run(
            ["git", "push", "origin", f":refs/tags/{TAG}"],
            repo,
            env,
            check=False,
        )
        assert deletion.returncode == 0, f"Remote tag deletion failed: {deletion.stderr}"

        after_local = local_snapshot(repo, env)
        after_remote_branches = bare_refs(remote, repo, env, "refs/heads/")
        after_remote_tags = bare_refs(remote, repo, env, "refs/tags/")
        remote_topic = bare_output(remote, ["rev-parse", "refs/heads/topic"], repo, env)
        remote_b_exists = run(
            ["git", f"--git-dir={remote}", "cat-file", "-e", commits["B"]],
            repo,
            env,
            check=False,
        )
        remote_b_commit = remote_b_exists.returncode == 0
        remote_url = remote.as_uri()

        assert deletion.returncode == 0
        assert before_remote_tags == [f"refs/tags/{TAG} {commits['B']}"]
        assert after_remote_tags == []
        assert before_local["tag_refs"] == after_local["tag_refs"] == [
            f"refs/tags/{TAG} {commits['B']}"
        ]
        assert before_local == after_local
        assert before_local["head"] == commits["C"]
        assert before_local["head_ref"] == "refs/heads/main"
        assert before_local["branch_refs"] == [
            f"refs/heads/main {commits['C']}", f"refs/heads/topic {commits['B']}"
        ]
        assert before_local["index_tree"] == after_local["index_tree"]
        assert before_local["staged_files"] == after_local["staged_files"] == []
        assert before_local["status"] == after_local["status"] == ""
        assert before_remote_branches == after_remote_branches
        assert remote_topic == commits["B"] and remote_b_commit

        actual = {
            "commit_ids": commits,
            "tag": TAG,
            "tag_target": commits["B"],
            "remote_url": "file://<temporary>/remote.git",
            "prediction": inputs["prediction"],
            "command": ["git", "push", "origin", f":refs/tags/{TAG}"],
            "command_returncode": deletion.returncode,
            "command_stdout": deletion.stdout.replace(remote_url, "file://<temporary>/remote.git"),
            "command_stderr": deletion.stderr.replace(remote_url, "file://<temporary>/remote.git"),
            "local_before": before_local,
            "local_after": after_local,
            "remote_branches_before": before_remote_branches,
            "remote_branches_after": after_remote_branches,
            "remote_tags_before": before_remote_tags,
            "remote_tags_after": after_remote_tags,
            "remote_topic_commit_after": remote_topic,
            "remote_commit_B_still_exists": remote_b_commit,
            "changed_object": f"refs/tags/{TAG} on origin",
            "answer": (
                f"Deleted origin's refs/tags/{TAG}; the local tag still points to B, and "
                "HEAD, branches, index, working tree, and remote branches are unchanged."
            ),
            "assertions": {
                "remote_tag_ref_was_present_before_and_absent_after": (
                    before_remote_tags == [f"refs/tags/{TAG} {commits['B']}"]
                    and after_remote_tags == []
                ),
                "local_tag_still_points_to_B": before_local["tag_refs"] == after_local["tag_refs"],
                "local_HEAD_branches_index_and_worktree_unchanged": before_local == after_local,
                "remote_branches_unchanged": before_remote_branches == after_remote_branches,
                "commit_B_still_exists_and_is_topic_tip": remote_b_commit and remote_topic == commits["B"],
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
    print("PASS: only the remote tag ref was deleted; local state and remote branches stayed unchanged")


if __name__ == "__main__":
    main()
