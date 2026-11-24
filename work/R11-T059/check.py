#!/usr/bin/env python3
"""Check prerequisites and state changes for `git push origin HEAD`."""

import json
import os
import pathlib
import subprocess
import tempfile


HERE = pathlib.Path(__file__).resolve().parent
AUTHOR_NAME = "Course Student"
AUTHOR_EMAIL = "student@example.invalid"
FIXED_DATE = "2001-01-01T00:00:00+00:00"


def run(args, cwd, env=None, check=True):
    """Run a command; checked child failures raise CalledProcessError."""
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


def remote_output(remote, args, cwd, env):
    return output(["git", f"--git-dir={remote}", *args], cwd, env)


def branch_tracking_config(repo, env):
    # No upstream is expected: the push command names its remote explicitly.
    result = run(
        ["git", "config", "--local", "--get-regexp", r"^branch\.topic\.(remote|merge)$"],
        repo,
        env,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    return result.stdout.strip()


def local_snapshot(repo, remote, env):
    configured_origin = output(["git", "remote", "get-url", "origin"], repo, env)
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
        "status": output(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"], repo, env
        ),
        "notes": (repo / "notes.txt").read_text(encoding="utf-8"),
        "todo": (repo / "todo.txt").read_text(encoding="utf-8")
        if (repo / "todo.txt").exists()
        else None,
        "local_user_name": output(["git", "config", "--local", "--get", "user.name"], repo, env),
        "local_user_email": output(["git", "config", "--local", "--get", "user.email"], repo, env),
        "origin_url": configured_origin.replace(remote.as_uri(), "file://<temporary>/remote.git"),
        "topic_tracking": branch_tracking_config(repo, env),
        "remote_refs": remote_output(
            remote,
            ["for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/"],
            repo,
            env,
        ).splitlines(),
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
            # Isolate the temporary fixture from the user's global Git config.
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
    run(["git", "switch", "topic"], repo, env)

    run(["git", "remote", "add", "origin", remote.as_uri()], repo, env)
    # A staged draft illustrates that push sends commits, not index contents.
    with (repo / "notes.txt").open("a", encoding="utf-8") as notes:
        notes.write("staged local draft\n")
    run(["git", "add", "notes.txt"], repo, env)

    assert output(["git", "rev-parse", "--show-toplevel"], repo, env) == str(repo.resolve())
    assert output(["git", "branch", "--show-current"], repo, env) == "topic"
    assert output(["git", "rev-parse", "main"], repo, env) == commit_c
    assert output(["git", "rev-parse", "topic"], repo, env) == commit_b
    assert output(["git", "rev-parse", "HEAD"], repo, env) == commit_b
    assert output(["git", "config", "--local", "--get", "user.name"], repo, env) == AUTHOR_NAME
    assert output(["git", "config", "--local", "--get", "user.email"], repo, env) == AUTHOR_EMAIL
    assert env["GIT_CONFIG_GLOBAL"] == os.devnull
    assert output(["git", "diff", "--cached", "--name-only"], repo, env).splitlines() == ["notes.txt"]
    assert output(["git", "diff", "--name-only"], repo, env) == ""
    assert remote_output(remote, ["for-each-ref", "--format=%(refname)", "refs/heads/"], repo, env) == ""

    return env, {"A": commit_a, "B": commit_b, "C": commit_c}


def main():
    inputs = {
        "author": {"name": AUTHOR_NAME, "email": AUTHOR_EMAIL},
        "history": {
            "A": "main creates notes.txt containing alpha\\n",
            "B": "topic appends beta\\n to notes.txt",
            "C": "main creates todo.txt containing one\\n",
        },
        "current_branch": "topic at commit B; main points to commit C",
        "remote": "second local bare repository configured as origin using file:// URL",
        "staged_change": "notes.txt includes a staged local draft after commit B; it must not be sent by the push",
        "local_config": ["user.name", "user.email", "remote.origin.url"],
        "global_config": "isolated with GIT_CONFIG_GLOBAL pointing at the null device; no global config writes",
        "operation": ["git", "push", "origin", "HEAD"],
    }
    expected = {
        "push_succeeds": True,
        "remote_topic_points_to_commit_B": True,
        "main_and_topic_local_refs_unchanged": True,
        "staged_edit_stays_local_and_is_not_pushed": True,
        "explicit_remote_means_upstream_tracking_not_required": True,
    }

    with tempfile.TemporaryDirectory(prefix="R11-T059-") as temporary:
        root = pathlib.Path(temporary)
        repo = root / "repo"
        remote = root / "remote.git"
        env, commits = make_fixture(repo, remote)

        before = local_snapshot(repo, remote, env)
        push = run(["git", "push", "origin", "HEAD"], repo, env, check=False)
        assert push.returncode == 0, f"git push failed: {push.stderr}"
        after = local_snapshot(repo, remote, env)
        remote_notes = remote_output(remote, ["show", "refs/heads/topic:notes.txt"], repo, env)
        remote_files = remote_output(remote, ["ls-tree", "-r", "--name-only", "refs/heads/topic"], repo, env).splitlines()
        remote_topic = remote_output(remote, ["rev-parse", "refs/heads/topic"], repo, env)
        push_stdout = push.stdout.replace(remote.as_uri(), "file://<temporary>/remote.git")
        push_stderr = push.stderr.replace(remote.as_uri(), "file://<temporary>/remote.git")

        assert before["head"] == commits["B"]
        assert before["head_ref"] == "refs/heads/topic"
        assert before["staged_files"] == ["notes.txt"]
        assert before["unstaged_files"] == []
        assert before["topic_tracking"] == ""
        assert before["remote_refs"] == []
        assert remote_topic == commits["B"]
        assert remote_notes == "alpha\nbeta"
        assert "staged local draft" not in remote_notes
        assert remote_files == ["notes.txt"]
        assert after["head"] == before["head"]
        assert after["head_ref"] == before["head_ref"]
        assert after["branch_refs"] == before["branch_refs"]
        assert after["index_tree"] == before["index_tree"]
        assert after["staged_files"] == before["staged_files"]
        assert after["unstaged_files"] == before["unstaged_files"]
        assert after["status"] == before["status"]
        assert after["notes"] == before["notes"]
        assert after["topic_tracking"] == before["topic_tracking"]

        actual = {
            "commit_ids": commits,
            "remote_url": "file://<temporary>/remote.git",
            "push_command": ["git", "push", "origin", "HEAD"],
            "push_returncode": push.returncode,
            "push_stdout": push_stdout,
            "push_stderr": push_stderr,
            "state_before": before,
            "state_after": after,
            "remote_result": {
                "topic_ref": remote_topic,
                "topic_files": remote_files,
                "notes_txt": remote_notes,
            },
            "assertions": {
                "repository_and_named_current_branch": (
                    before["head_ref"] == "refs/heads/topic"
                    and before["head"] == commits["B"]
                ),
                "required_local_identity_and_origin_configured": (
                    before["local_user_name"] == AUTHOR_NAME
                    and before["local_user_email"] == AUTHOR_EMAIL
                    and before["origin_url"] == "file://<temporary>/remote.git"
                    and env["GIT_CONFIG_GLOBAL"] == os.devnull
                ),
                "staged_change_present_before_push": before["staged_files"] == ["notes.txt"],
                "push_succeeded_and_remote_topic_is_B": push.returncode == 0 and remote_topic == commits["B"],
                "staged_edit_was_not_pushed": "staged local draft" not in remote_notes,
                "local_state_unchanged": (
                    after["head"] == before["head"]
                    and after["branch_refs"] == before["branch_refs"]
                    and after["index_tree"] == before["index_tree"]
                    and after["status"] == before["status"]
                ),
                "upstream_tracking_not_required": before["topic_tracking"] == after["topic_tracking"] == "",
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
    print("PASS: push prerequisites, destination branch, staged-content boundary, and unchanged local state")


if __name__ == "__main__":
    main()
