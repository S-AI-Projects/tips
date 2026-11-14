#!/usr/bin/env python3
"""Show recovery after sparse-checkout rules hide a committed file."""

import json
import os
import pathlib
import subprocess
import tempfile


HERE = pathlib.Path(__file__).resolve().parent
AUTHOR_NAME = "Course Student"
AUTHOR_EMAIL = "student@example.invalid"


def run(args, *, cwd, env=None):
    result = subprocess.run(
        args, cwd=cwd, env=env, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def snapshot(repo):
    branch_refs = run(
        ["git", "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/"],
        cwd=repo,
    ).splitlines()
    tracked = run(["git", "ls-files", "--cached", "-z"], cwd=repo).split("\0")
    contents = {}
    for name in filter(None, tracked):
        path = repo / name
        contents[name] = path.read_bytes().decode("utf-8") if path.is_file() else None
    return {
        "head": run(["git", "rev-parse", "HEAD"], cwd=repo),
        "head_ref": run(["git", "symbolic-ref", "-q", "HEAD"], cwd=repo),
        "branch_refs": branch_refs,
        "tree": run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo),
        "index_tree": run(["git", "write-tree"], cwd=repo),
        "staged_files": run(["git", "diff", "--cached", "--name-only"], cwd=repo).splitlines(),
        "unstaged_files": run(["git", "diff", "--name-only"], cwd=repo).splitlines(),
        "working_tree_files": contents,
        "status": run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=repo),
    }


def main():
    inputs = {
        "clone_command": "git clone --filter=blob:none --sparse <file-url> <checkout>",
        "mistake": "git sparse-checkout set --no-cone notes.txt",
        "recovery": "git sparse-checkout set --no-cone notes.txt todo.txt",
        "author": {"name": AUTHOR_NAME, "email": AUTHOR_EMAIL},
        "commits": {
            "A": "create notes.txt containing alpha\\n",
            "B": "append beta\\n to notes.txt",
            "C": "create todo.txt containing one\\n",
        },
        "branches": {"main": "commit C", "topic": "commit B"},
    }
    expected = {
        "mistake": "todo.txt is absent from the sparse working tree but remains in commit C.",
        "recovery": "Both committed files return with their expected contents; HEAD, branch refs, and committed tree remain unchanged.",
        "limitation": "Sparse checkout cannot recover uncommitted edits to a path removed from the working tree.",
    }

    with tempfile.TemporaryDirectory(prefix="R11-T053-") as tmp:
        root = pathlib.Path(tmp)
        source = root / "source"
        source.mkdir()
        env = os.environ.copy()
        env.update({
            "GIT_AUTHOR_NAME": AUTHOR_NAME,
            "GIT_AUTHOR_EMAIL": AUTHOR_EMAIL,
            "GIT_COMMITTER_NAME": AUTHOR_NAME,
            "GIT_COMMITTER_EMAIL": AUTHOR_EMAIL,
        })

        run(["git", "init", "-b", "main"], cwd=source, env=env)
        run(["git", "config", "user.name", AUTHOR_NAME], cwd=source, env=env)
        run(["git", "config", "user.email", AUTHOR_EMAIL], cwd=source, env=env)

        (source / "notes.txt").write_text("alpha\n", encoding="utf-8")
        run(["git", "add", "notes.txt"], cwd=source, env=env)
        run(["git", "commit", "-m", "A: add alpha"], cwd=source, env=env)
        commit_a = run(["git", "rev-parse", "HEAD"], cwd=source)

        with (source / "notes.txt").open("a", encoding="utf-8") as notes:
            notes.write("beta\n")
        run(["git", "add", "notes.txt"], cwd=source, env=env)
        run(["git", "commit", "-m", "B: add beta"], cwd=source, env=env)
        commit_b = run(["git", "rev-parse", "HEAD"], cwd=source)

        (source / "todo.txt").write_text("one\n", encoding="utf-8")
        run(["git", "add", "todo.txt"], cwd=source, env=env)
        run(["git", "commit", "-m", "C: add todo"], cwd=source, env=env)
        commit_c = run(["git", "rev-parse", "HEAD"], cwd=source)
        run(["git", "branch", "topic", commit_b], cwd=source, env=env)

        bare = root / "remote.git"
        run(["git", "clone", "--bare", str(source), str(bare)], cwd=root, env=env)
        run(["git", "config", "uploadpack.allowFilter", "true"], cwd=bare, env=env)
        checkout = root / "checkout"
        remote_url = bare.as_uri()
        run(["git", "clone", "--filter=blob:none", "--sparse", remote_url, str(checkout)], cwd=root, env=env)
        run(["git", "fetch", "origin", "topic"], cwd=checkout, env=env)
        run(["git", "branch", "topic", "FETCH_HEAD"], cwd=checkout, env=env)

        before = snapshot(checkout)
        expected_files = {"notes.txt": "alpha\nbeta\n", "todo.txt": "one\n"}

        # The mistaken file-only sparse pattern hides todo.txt from the checkout.
        run(["git", "sparse-checkout", "set", "--no-cone", "notes.txt"], cwd=checkout, env=env)
        after_mistake = snapshot(checkout)
        tracked_in_commit = run(["git", "ls-tree", "--name-only", "HEAD"], cwd=checkout).splitlines()
        assert after_mistake["head"] == before["head"] and after_mistake["head_ref"] == before["head_ref"]
        assert after_mistake["branch_refs"] == before["branch_refs"]
        assert after_mistake["tree"] == before["tree"] and after_mistake["index_tree"] == before["index_tree"]

        # Recover by setting the sparse list to include both committed root files.
        run(["git", "sparse-checkout", "set", "--no-cone", "notes.txt", "todo.txt"], cwd=checkout, env=env)
        after_recovery = snapshot(checkout)
        sparse_patterns = run(["git", "sparse-checkout", "list"], cwd=checkout).splitlines()

        # Check the missing file was only hidden, then verify the saved commit/tree,
        # branch pointers, expected contents, and clean state after recovery.
        assert "notes.txt" in after_mistake["working_tree_files"] and after_mistake["working_tree_files"]["notes.txt"] is not None
        assert after_mistake["working_tree_files"]["todo.txt"] is None and "todo.txt" in tracked_in_commit
        assert after_recovery["head"] == before["head"] == commit_c and after_recovery["head_ref"] == "refs/heads/main"
        assert after_recovery["branch_refs"] == before["branch_refs"] and f"refs/heads/topic {commit_b}" in after_recovery["branch_refs"]
        assert after_recovery["tree"] == before["tree"] and after_recovery["index_tree"] == before["index_tree"]
        assert after_recovery["working_tree_files"] == expected_files
        assert after_recovery["status"] == "" and after_recovery["staged_files"] == [] and after_recovery["unstaged_files"] == []
        assert {line.lstrip("/") for line in sparse_patterns} == {"notes.txt", "todo.txt"}

        actual = {
            "commit_ids": {"A": commit_a, "B": commit_b, "C": commit_c},
            "before": before,
            "after_mistake": after_mistake,
            "tracked_paths_in_commit_c": tracked_in_commit,
            "after_recovery": after_recovery,
            "sparse_patterns_after_recovery": sparse_patterns,
            "assertions": {
                "mistake_hid_todo_without_removing_it_from_commit": after_mistake["working_tree_files"]["todo.txt"] is None and "todo.txt" in tracked_in_commit,
                "mistake_did_not_change_head_refs_or_index_tree": after_mistake["head"] == before["head"] and after_mistake["branch_refs"] == before["branch_refs"] and after_mistake["index_tree"] == before["index_tree"],
                "head_and_branch_refs_unchanged": after_recovery["head"] == before["head"] and after_recovery["branch_refs"] == before["branch_refs"],
                "saved_tree_restored": after_recovery["tree"] == before["tree"] and after_recovery["index_tree"] == before["index_tree"],
                "expected_files_restored_and_clean": after_recovery["working_tree_files"] == expected_files and after_recovery["status"] == "",
                "sparse_list_contains_both_files": {line.lstrip("/") for line in sparse_patterns} == {"notes.txt", "todo.txt"},
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
    print("PASS: sparse-checkout mistake recovered with the original commit, tree, refs, and files")


if __name__ == "__main__":
    main()
