#!/usr/bin/env python3
"""Compare a local topic branch before and after rebase with range-diff."""

import json
import os
import pathlib
import re
import subprocess
import tempfile


HERE = pathlib.Path(__file__).resolve().parent
AUTHOR_NAME = "Course Student"
AUTHOR_EMAIL = "student@example.invalid"


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
        "remote_tracking_refs": run(
            ["git", "for-each-ref", "--format=%(refname) %(objectname)", "refs/remotes/"],
            cwd=repo,
        ).splitlines(),
        "index_tree": run(["git", "write-tree"], cwd=repo),
        "staged_files": run(["git", "diff", "--cached", "--name-only"], cwd=repo).splitlines(),
        "unstaged_files": run(["git", "diff", "--name-only"], cwd=repo).splitlines(),
        "untracked_files": run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=repo
        ).splitlines(),
        "files": {
            name: (repo / name).read_text(encoding="utf-8")
            for name in ("notes.txt", "todo.txt")
        },
        "status": run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=repo),
    }


def main():
    inputs = {
        "author": {"name": AUTHOR_NAME, "email": AUTHOR_EMAIL},
        "history": {
            "A": "main starts at A: notes.txt contains alpha\\n",
            "B": "topic adds beta\\n to notes.txt",
            "C": "main adds todo.txt containing one\\n",
        },
        "comparison_command": "git range-diff --no-color origin/main^..topic-before-rebase origin/main..topic",
        "local_branches": ["main", "topic", "topic-before-rebase"],
        "remote_tracking_ref": "origin/main (from a temporary file:// bare repository)",
    }
    expected = {
        "rebase": "local topic moves to a rewritten commit on origin/main; local main, origin/main, and topic-before-rebase stay fixed.",
        "range_diff": "The old and rebased beta commits are paired as equivalent (the output line contains '='); range-diff itself changes no refs, index, or working-tree files.",
        "remote": "Only a temporary local file:// remote is configured; no public remote or personal branch is used.",
    }

    with tempfile.TemporaryDirectory(prefix="R11-T054-") as tmp:
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

        run(["git", "switch", "-c", "topic"], cwd=repo, env=env)
        with (repo / "notes.txt").open("a", encoding="utf-8") as notes:
            notes.write("beta\n")
        run(["git", "add", "notes.txt"], cwd=repo, env=env)
        run(["git", "commit", "-m", "B: add beta"], cwd=repo, env=env)
        old_topic = run(["git", "rev-parse", "HEAD"], cwd=repo)

        run(["git", "switch", "main"], cwd=repo, env=env)
        (repo / "todo.txt").write_text("one\n", encoding="utf-8")
        run(["git", "add", "todo.txt"], cwd=repo, env=env)
        run(["git", "commit", "-m", "C: add todo"], cwd=repo, env=env)
        commit_c = run(["git", "rev-parse", "HEAD"], cwd=repo)
        run(["git", "branch", "topic-before-rebase", old_topic], cwd=repo, env=env)
        main_before_rebase = run(["git", "rev-parse", "main"], cwd=repo)
        old_snapshot_ref = run(["git", "rev-parse", "topic-before-rebase"], cwd=repo)

        bare = pathlib.Path(tmp) / "remote.git"
        run(["git", "clone", "--bare", str(repo), str(bare)], cwd=tmp, env=env)
        run(["git", "remote", "add", "origin", bare.as_uri()], cwd=repo, env=env)
        run(["git", "fetch", "origin"], cwd=repo, env=env)
        origin_main = run(["git", "rev-parse", "origin/main"], cwd=repo)
        remote_refs_before_search = run(
            ["git", "--git-dir", str(bare), "show-ref"], cwd=repo
        ).splitlines()

        run(["git", "switch", "topic"], cwd=repo, env=env)
        run(["git", "rebase", "origin/main"], cwd=repo, env=env)
        rebased_topic = run(["git", "rev-parse", "topic"], cwd=repo)
        before_search = snapshot(repo)
        remotes = run(["git", "remote", "-v"], cwd=repo)

        range_diff = run(
            [
                "git", "range-diff", "--no-color",
                "origin/main^..topic-before-rebase", "origin/main..topic",
            ],
            cwd=repo,
            env=env,
        )
        after_search = snapshot(repo)
        remote_refs_after_search = run(
            ["git", "--git-dir", str(bare), "show-ref"], cwd=repo
        ).splitlines()
        matched_equivalent_commit = bool(
            re.search(
                r"^\s*1:\s+[0-9a-f]+\s+=\s+1:\s+[0-9a-f]+\s+B: add beta$",
                range_diff,
                re.MULTILINE,
            )
        )

        # Rebase changes only the local topic ref among the refs being compared.
        assert old_topic != rebased_topic
        assert main_before_rebase == commit_c
        assert origin_main == commit_c
        assert old_snapshot_ref == old_topic
        assert before_search["head"] == rebased_topic
        assert before_search["head_ref"] == "refs/heads/topic"
        assert "refs/heads/main " + main_before_rebase in before_search["branch_refs"]
        assert "refs/heads/topic-before-rebase " + old_snapshot_ref in before_search["branch_refs"]
        assert "refs/remotes/origin/main " + origin_main in before_search["remote_tracking_refs"]

        # The range-diff output pairs the old and rebased versions of commit B.
        assert matched_equivalent_commit, range_diff
        assert after_search["head"] == before_search["head"]
        assert after_search["head_ref"] == before_search["head_ref"]
        assert after_search["branch_refs"] == before_search["branch_refs"]
        assert after_search["remote_tracking_refs"] == before_search["remote_tracking_refs"]
        assert remote_refs_after_search == remote_refs_before_search
        assert after_search["index_tree"] == before_search["index_tree"]
        assert after_search["files"] == before_search["files"] == {
            "notes.txt": "alpha\nbeta\n",
            "todo.txt": "one\n",
        }
        assert after_search["status"] == before_search["status"] == ""
        assert "origin\t" + bare.as_uri() + " (fetch)" in remotes.splitlines()

        actual = {
            "commit_ids": {"A": commit_a, "B_old_topic": old_topic, "C": commit_c, "B_rebased": rebased_topic},
            "main_before_rebase": main_before_rebase,
            "origin_main_before_rebase": origin_main,
            "topic_before_rebase_snapshot": old_snapshot_ref,
            "before_range_diff": before_search,
            "after_range_diff": after_search,
            "range_diff_output": range_diff,
            "remotes": remotes.splitlines(),
            "local_bare_remote_refs_before_range_diff": remote_refs_before_search,
            "local_bare_remote_refs_after_range_diff": remote_refs_after_search,
            "assertions": {
                "rebase_moved_topic_ref": old_topic != rebased_topic,
                "head_is_on_rebased_local_topic": before_search["head"] == rebased_topic and before_search["head_ref"] == "refs/heads/topic",
                "main_remote_tracking_and_saved_old_topic_refs_stayed_fixed": (
                    main_before_rebase == commit_c and origin_main == commit_c and old_snapshot_ref == old_topic
                ),
                "range_diff_paired_equivalent_commit_b": matched_equivalent_commit,
                "range_diff_left_head_refs_index_and_files_unchanged": (
                    after_search["head"] == before_search["head"]
                    and after_search["head_ref"] == before_search["head_ref"]
                    and after_search["branch_refs"] == before_search["branch_refs"]
                    and after_search["remote_tracking_refs"] == before_search["remote_tracking_refs"]
                    and after_search["index_tree"] == before_search["index_tree"]
                    and after_search["files"] == before_search["files"]
                ),
                "temporary_remote_did_not_change_during_range_diff": remote_refs_after_search == remote_refs_before_search,
                "remote_is_file_url_local_only": "origin\t" + bare.as_uri() + " (fetch)" in remotes.splitlines(),
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
    print("PASS: range-diff paired the rebased topic commit and left repository state unchanged")


if __name__ == "__main__":
    main()
