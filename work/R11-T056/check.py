#!/usr/bin/env python3
"""Compare clearing every stash with dropping each stash from a temporary repo."""

import json
import os
import pathlib
import subprocess
import tempfile


HERE = pathlib.Path(__file__).resolve().parent
AUTHOR_NAME = "Course Student"
AUTHOR_EMAIL = "student@example.invalid"
STASH_COUNT = 3


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


def stash_ref(repo):
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "refs/stash"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    if result.returncode == 1:
        return None
    raise subprocess.CalledProcessError(
        result.returncode, result.args, result.stdout, result.stderr
    )


def capture(repo):
    stash_ids = run(["git", "stash", "list", "--format=%H"], cwd=repo).splitlines()
    stash_subjects = run(["git", "stash", "list", "--format=%gs"], cwd=repo).splitlines()
    branch_refs = run(
        ["git", "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/"],
        cwd=repo,
    ).splitlines()
    return {
        "git_state": {
            "head": run(["git", "rev-parse", "HEAD"], cwd=repo),
            "head_ref": run(["git", "symbolic-ref", "-q", "HEAD"], cwd=repo),
            "head_tree": run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo),
            "branch_refs": branch_refs,
            "branch_trees": {
                branch: run(["git", "rev-parse", f"{branch}^{{tree}}"], cwd=repo)
                for branch in ("main", "topic")
            },
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
        },
        "stash_ids": stash_ids,
        "stash_subjects": stash_subjects,
        "stash_ref": stash_ref(repo),
    }


def fixture_signature(snapshot):
    state = snapshot["git_state"]
    return {
        "head_ref": state["head_ref"],
        "head_tree": state["head_tree"],
        "branch_names": [line.split()[0] for line in state["branch_refs"]],
        "branch_trees": state["branch_trees"],
        "index_tree": state["index_tree"],
        "staged_files": state["staged_files"],
        "unstaged_files": state["unstaged_files"],
        "untracked_files": state["untracked_files"],
        "files": state["files"],
        "status": state["status"],
        "stash_count": len(snapshot["stash_ids"]),
        "stash_subjects": snapshot["stash_subjects"],
    }


def make_fixture(repo):
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
    commit_b = run(["git", "rev-parse", "HEAD"], cwd=repo)

    run(["git", "switch", "main"], cwd=repo, env=env)
    (repo / "todo.txt").write_text("one\n", encoding="utf-8")
    run(["git", "add", "todo.txt"], cwd=repo, env=env)
    run(["git", "commit", "-m", "C: add todo"], cwd=repo, env=env)
    commit_c = run(["git", "rev-parse", "HEAD"], cwd=repo)

    assert run(["git", "rev-parse", "topic"], cwd=repo) == commit_b
    assert run(["git", "rev-parse", "main"], cwd=repo) == commit_c

    # Store three distinct tracked changes, restoring a clean checkout after each.
    for index, filename in enumerate(("notes.txt", "todo.txt", "notes.txt"), start=1):
        path = repo / filename
        with path.open("a", encoding="utf-8") as changed:
            changed.write(f"saved-change-{index}\n")
        run(["git", "stash", "push", "-m", f"saved-change-{index}"], cwd=repo, env=env)
        assert run(["git", "status", "--porcelain=v1"], cwd=repo) == ""

    # Leave current staged and unstaged edits in place to prove both operations
    # only change stash refs and do not apply or discard the current work.
    with (repo / "notes.txt").open("a", encoding="utf-8") as notes:
        notes.write("current-staged\n")
    run(["git", "add", "notes.txt"], cwd=repo, env=env)
    with (repo / "notes.txt").open("a", encoding="utf-8") as notes:
        notes.write("current-unstaged\n")

    assert not run(["git", "remote", "-v"], cwd=repo)
    return env, {"A": commit_a, "B": commit_b, "C": commit_c}


def run_clear(repo, env):
    before = capture(repo)
    assert len(before["stash_ids"]) == STASH_COUNT
    command_output = run(["git", "stash", "clear"], cwd=repo, env=env)
    after = capture(repo)
    assert after["stash_ids"] == []
    assert after["stash_subjects"] == []
    assert after["stash_ref"] is None
    assert after["git_state"] == before["git_state"]
    return {"before": before, "command_output": command_output, "after": after}


def run_repeated_drop(repo, env):
    before = capture(repo)
    assert len(before["stash_ids"]) == STASH_COUNT
    remaining = before["stash_ids"][:]
    steps = []
    for _ in range(STASH_COUNT):
        dropped_id = remaining[0]
        command_output = run(["git", "stash", "drop", "stash@{0}"], cwd=repo, env=env)
        remaining = remaining[1:]
        after_step = capture(repo)
        assert after_step["stash_ids"] == remaining
        assert after_step["stash_ref"] == (remaining[0] if remaining else None)
        assert after_step["git_state"] == before["git_state"]
        steps.append({
            "dropped_id": dropped_id,
            "command_output": command_output,
            "remaining_ids": after_step["stash_ids"],
            "remaining_count": len(after_step["stash_ids"]),
            "stash_ref": after_step["stash_ref"],
            "git_state_unchanged": after_step["git_state"] == before["git_state"],
        })
    after = capture(repo)
    assert after["stash_ids"] == []
    assert after["stash_subjects"] == []
    assert after["stash_ref"] is None
    return {"before": before, "steps": steps, "after": after}


def main():
    inputs = {
        "author": {"name": AUTHOR_NAME, "email": AUTHOR_EMAIL},
        "history": {
            "A": "main creates notes.txt containing alpha\\n",
            "B": "topic appends beta\\n to notes.txt",
            "C": "main adds todo.txt containing one\\n",
        },
        "initial_stashes": STASH_COUNT,
        "comparison": [
            "git stash clear",
            "repeat git stash drop 'stash@{0}' until git stash list is empty",
        ],
        "current_worktree_before_removal": "notes.txt has staged and unstaged edits; stash deletion must preserve both.",
        "remote": "none; all operations run in temporary repositories",
    }
    expected = {
        "starting_condition": "Both temporary repositories have the same main/topic history, three stashes, and equivalent staged and unstaged edits.",
        "clear": "All three stash entries and refs/stash disappear in one command.",
        "drop": "Each command removes one top entry; the list counts go 2, 1, 0 and refs/stash advances to the next entry before disappearing.",
        "shared_result": "HEAD, branch refs, commit tree, index, and working-tree files are unchanged by either workflow.",
    }

    with tempfile.TemporaryDirectory(prefix="R11-T056-") as tmp:
        root = pathlib.Path(tmp)
        clear_repo = root / "clear-workflow"
        drop_repo = root / "drop-workflow"
        clear_env, clear_commits = make_fixture(clear_repo)
        drop_env, drop_commits = make_fixture(drop_repo)

        clear_before = capture(clear_repo)
        drop_before = capture(drop_repo)
        assert fixture_signature(clear_before) == fixture_signature(drop_before)
        assert len(clear_before["stash_ids"]) == len(drop_before["stash_ids"]) == STASH_COUNT

        clear_result = run_clear(clear_repo, clear_env)
        drop_result = run_repeated_drop(drop_repo, drop_env)
        assert [step["remaining_count"] for step in drop_result["steps"]] == [2, 1, 0]
        assert all(step["git_state_unchanged"] for step in drop_result["steps"])
        assert clear_result["after"]["git_state"] == drop_result["after"]["git_state"]
        assert clear_result["after"]["stash_ids"] == drop_result["after"]["stash_ids"] == []
        assert clear_result["after"]["stash_ref"] is drop_result["after"]["stash_ref"] is None

        actual = {
            "commit_ids": {"clear_fixture": clear_commits, "drop_fixture": drop_commits},
            "equivalent_initial_fixture_signature": fixture_signature(clear_before),
            "clear_workflow": clear_result,
            "drop_workflow": drop_result,
            "assertions": {
                "fixtures_start_equivalent": fixture_signature(clear_before) == fixture_signature(drop_before),
                "clear_removes_all_stashes_at_once": (
                    len(clear_result["before"]["stash_ids"]) == STASH_COUNT
                    and clear_result["after"]["stash_ids"] == []
                    and clear_result["after"]["stash_ref"] is None
                ),
                "drop_removes_one_entry_per_step": [
                    step["remaining_count"] for step in drop_result["steps"]
                ] == [2, 1, 0],
                "stash_ref_advances_between_drops": (
                    drop_result["steps"][0]["stash_ref"] == drop_result["steps"][1]["dropped_id"]
                    and drop_result["steps"][1]["stash_ref"] == drop_result["steps"][2]["dropped_id"]
                    and drop_result["steps"][2]["stash_ref"] is None
                ),
                "clear_preserves_head_branches_index_and_worktree": (
                    clear_result["before"]["git_state"] == clear_result["after"]["git_state"]
                ),
                "drop_preserves_head_branches_index_and_worktree_each_step": all(
                    step["git_state_unchanged"] for step in drop_result["steps"]
                ),
                "both_workflows_reach_the_same_empty_stash_state": (
                    clear_result["after"]["stash_ids"] == drop_result["after"]["stash_ids"] == []
                    and clear_result["after"]["git_state"] == drop_result["after"]["git_state"]
                ),
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
    print("PASS: clear and repeated drop empty equivalent stash lists without changing current work")


if __name__ == "__main__":
    main()
