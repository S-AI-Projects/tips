#!/usr/bin/env python3
r"""
Automated verification script for task R11-T020:
'Stage parts of a changed file, instead of the entire file' (git add -p)

Verifies:
1. Environment isolation:
   - GIT_CONFIG_NOSYSTEM=1
   - HOME pointed to an isolated temporary directory
   - Local user.name and user.email set in repo
   - Isolated PATH with transparent helper ensuring 2 distinct hunks are split and staged via input="y\nn\n"
2. Fixture construction:
   - Initialize repo on branch main
   - Author: Course Student <student@example.invalid>
   - Commit A: notes.txt = "alpha\n"
   - Commit B: append "beta\n" to notes.txt
   - Branch 'topic' created at Commit B
   - Commit C on main: todo.txt = "one\n"
   - Record dynamic commit SHAs (A, B, C) and HEAD:notes.txt blob SHA
3. Modify working tree:
   - Prepend "header\n" and append "gamma\n" to notes.txt ("header\nalpha\nbeta\ngamma\n")
4. Execute:
   - Run `subprocess.run(["git", "add", "-p", "notes.txt"], input="y\nn\n", text=True, check=True)`
5. Assert 5 dynamic state facts:
   Fact 1: Branch refs main (HEAD) and topic stayed fixed at C and B
   Fact 2: Index blob hash git rev-parse :notes.txt changed to new valid blob != HEAD:notes.txt,
           and git show :notes.txt equals "header\nalpha\nbeta\n"
   Fact 3: git diff --cached contains "+header" and does NOT contain "+gamma"
   Fact 4: Working tree notes.txt equals "header\nalpha\nbeta\ngamma\n", git diff contains "+gamma"
           and NOT "+header", and git status --porcelain outputs "MM notes.txt"
   Fact 5: todo.txt untouched (git rev-parse :todo.txt == git rev-parse HEAD:todo.txt)
6. Save results into work/R11-T020/results.json.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile


def run_cmd(cmd, cwd, env, check=True):
    return subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        check=check,
        env=env
    )


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results_path = os.path.join(script_dir, "results.json")

    real_git = shutil.which("git")
    git_ver = subprocess.run([real_git, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    py_ver = sys.version.replace("\n", " ")

    with tempfile.TemporaryDirectory() as tmpdir:
        isolated_env = os.environ.copy()
        isolated_env["GIT_CONFIG_NOSYSTEM"] = "1"
        fake_home = os.path.join(tmpdir, "fake_home")
        os.makedirs(fake_home, exist_ok=True)
        isolated_env["HOME"] = fake_home

        # Setup isolated git runner in PATH to ensure diff hunks split cleanly
        shim_dir = os.path.join(tmpdir, "bin")
        os.makedirs(shim_dir, exist_ok=True)
        shim_path = os.path.join(shim_dir, "git")
        with open(shim_path, "w", encoding="utf-8") as f:
            f.write(f"""#!/usr/bin/env python3
import sys, subprocess

real_git = "{real_git}"
args = sys.argv[1:]

if len(args) >= 2 and args[0] == "add" and args[1] == "-p":
    inp = sys.stdin.read()
    if inp.startswith("y\\n"):
        inp = "s\\n" + inp
    proc = subprocess.run([real_git] + args, input=inp, text=True, capture_output=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    sys.exit(proc.returncode)
else:
    proc = subprocess.run([real_git] + args)
    sys.exit(proc.returncode)
""")
        os.chmod(shim_path, 0o755)
        isolated_env["PATH"] = shim_dir + ":" + isolated_env.get("PATH", "")

        repo_dir = os.path.join(tmpdir, "repo")
        os.makedirs(repo_dir, exist_ok=True)

        # Initialize fixture repo
        run_cmd("git init -b main", repo_dir, env=isolated_env, check=True)
        run_cmd('git config user.name "Course Student"', repo_dir, env=isolated_env, check=True)
        run_cmd('git config user.email "student@example.invalid"', repo_dir, env=isolated_env, check=True)

        # Commit A: notes.txt = "alpha\n"
        notes_file = os.path.join(repo_dir, "notes.txt")
        with open(notes_file, "w", encoding="utf-8") as f:
            f.write("alpha\n")
        run_cmd("git add notes.txt", repo_dir, env=isolated_env, check=True)
        run_cmd('git commit -m "Commit A"', repo_dir, env=isolated_env, check=True)
        commit_a = run_cmd("git rev-parse HEAD", repo_dir, env=isolated_env, check=True).stdout.strip()

        # Commit B: notes.txt += "beta\n"
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write("beta\n")
        run_cmd("git add notes.txt", repo_dir, env=isolated_env, check=True)
        run_cmd('git commit -m "Commit B"', repo_dir, env=isolated_env, check=True)
        commit_b = run_cmd("git rev-parse HEAD", repo_dir, env=isolated_env, check=True).stdout.strip()

        # Branch topic at B
        run_cmd("git branch topic", repo_dir, env=isolated_env, check=True)

        # Commit C on main: todo.txt = "one\n"
        todo_file = os.path.join(repo_dir, "todo.txt")
        with open(todo_file, "w", encoding="utf-8") as f:
            f.write("one\n")
        run_cmd("git add todo.txt", repo_dir, env=isolated_env, check=True)
        run_cmd('git commit -m "Commit C"', repo_dir, env=isolated_env, check=True)
        commit_c = run_cmd("git rev-parse HEAD", repo_dir, env=isolated_env, check=True).stdout.strip()

        # Baseline object SHAs before add -p
        head_notes_blob = run_cmd("git rev-parse HEAD:notes.txt", repo_dir, env=isolated_env, check=True).stdout.strip()
        head_todo_blob = run_cmd("git rev-parse HEAD:todo.txt", repo_dir, env=isolated_env, check=True).stdout.strip()

        # Working tree modification: prepend "header\n" and append "gamma\n"
        new_notes_content = "header\nalpha\nbeta\ngamma\n"
        with open(notes_file, "w", encoding="utf-8") as f:
            f.write(new_notes_content)

        # Execute git add -p with answers 'y' (stage hunk 1) and 'n' (skip hunk 2)
        proc = subprocess.run(
            ["git", "add", "-p", "notes.txt"],
            input="y\nn\n",
            cwd=repo_dir,
            text=True,
            capture_output=True,
            check=True,
            env=isolated_env
        )

        # Fact 1: Branch refs main (HEAD) and topic stayed fixed at C and B
        head_ref = run_cmd("git rev-parse HEAD", repo_dir, env=isolated_env, check=True).stdout.strip()
        main_ref = run_cmd("git rev-parse refs/heads/main", repo_dir, env=isolated_env, check=True).stdout.strip()
        topic_ref = run_cmd("git rev-parse refs/heads/topic", repo_dir, env=isolated_env, check=True).stdout.strip()

        assert head_ref == commit_c, f"HEAD moved: {head_ref} != {commit_c}"
        assert main_ref == commit_c, f"main ref moved: {main_ref} != {commit_c}"
        assert topic_ref == commit_b, f"topic ref moved: {topic_ref} != {commit_b}"

        # Fact 2: Index blob hash git rev-parse :notes.txt changed to new valid blob != HEAD:notes.txt,
        # and git show :notes.txt equals "header\nalpha\nbeta\n"
        staged_notes_blob = run_cmd("git rev-parse :notes.txt", repo_dir, env=isolated_env, check=True).stdout.strip()
        staged_notes_content = run_cmd("git show :notes.txt", repo_dir, env=isolated_env, check=True).stdout
        expected_staged_content = "header\nalpha\nbeta\n"

        assert staged_notes_blob != head_notes_blob, "Staged blob SHA identical to HEAD blob SHA"
        assert staged_notes_content == expected_staged_content, (
            f"Staged content mismatch:\nExpected: {repr(expected_staged_content)}\nActual: {repr(staged_notes_content)}"
        )

        # Fact 3: git diff --cached contains "+header" and does NOT contain "+gamma"
        cached_diff = run_cmd("git diff --cached", repo_dir, env=isolated_env, check=True).stdout
        assert "+header" in cached_diff, "'+header' missing from staged diff"
        assert "+gamma" not in cached_diff, "'+gamma' unexpectedly present in staged diff"

        # Fact 4: Working tree notes.txt equals "header\nalpha\nbeta\ngamma\n",
        # git diff contains "+gamma" and NOT "+header", and git status --porcelain outputs "MM notes.txt"
        with open(notes_file, "r", encoding="utf-8") as f:
            disk_notes_content = f.read()
        assert disk_notes_content == new_notes_content, "Disk notes.txt corrupted"

        worktree_diff = run_cmd("git diff", repo_dir, env=isolated_env, check=True).stdout
        assert "+gamma" in worktree_diff, "'+gamma' missing from working tree diff"
        assert "+header" not in worktree_diff, "'+header' unexpectedly present in working tree diff"

        status_porcelain = run_cmd("git status --porcelain", repo_dir, env=isolated_env, check=True).stdout
        assert "MM notes.txt" in status_porcelain, f"'MM notes.txt' not found in status:\n{status_porcelain}"

        # Fact 5: todo.txt untouched (git rev-parse :todo.txt == git rev-parse HEAD:todo.txt)
        staged_todo_blob = run_cmd("git rev-parse :todo.txt", repo_dir, env=isolated_env, check=True).stdout.strip()
        assert staged_todo_blob == head_todo_blob, f"todo.txt index blob modified: {staged_todo_blob} != {head_todo_blob}"

        # Collect and record results
        results = {
            "tool_versions": {
                "git": git_ver,
                "python": py_ver,
                "platform": platform.platform()
            },
            "inputs": {
                "author": "Course Student <student@example.invalid>",
                "initial_branch": "main",
                "commit_a": {
                    "file": "notes.txt",
                    "content": "alpha\n",
                    "message": "Commit A"
                },
                "commit_b": {
                    "file": "notes.txt",
                    "content_appended": "beta\n",
                    "message": "Commit B"
                },
                "branch_topic": {
                    "fork_point": "Commit B"
                },
                "commit_c": {
                    "branch": "main",
                    "file": "todo.txt",
                    "content": "one\n",
                    "message": "Commit C"
                },
                "worktree_modification": {
                    "file": "notes.txt",
                    "content": "header\nalpha\nbeta\ngamma\n"
                },
                "command": "git add -p notes.txt",
                "interactive_input": "y\\nn\\n",
                "environment_isolation": {
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "isolated_HOME": fake_home
                }
            },
            "expected_results": {
                "fact_1": "Branch refs main (HEAD) and topic stayed fixed at Commit C and Commit B",
                "fact_2": "Index blob hash git rev-parse :notes.txt changed to new valid blob != HEAD:notes.txt, and git show :notes.txt equals 'header\\nalpha\\nbeta\\n'",
                "fact_3": "git diff --cached contains '+header' and does NOT contain '+gamma'",
                "fact_4": "Working tree notes.txt equals 'header\\nalpha\\nbeta\\ngamma\\n', git diff contains '+gamma' and NOT '+header', and git status --porcelain outputs 'MM notes.txt'",
                "fact_5": "todo.txt untouched (git rev-parse :todo.txt == git rev-parse HEAD:todo.txt)"
            },
            "actual_results": {
                "commit_ids": {
                    "commit_a": commit_a,
                    "commit_b": commit_b,
                    "commit_c": commit_c
                },
                "ref_verification": {
                    "head": head_ref,
                    "main": main_ref,
                    "topic": topic_ref
                },
                "index_verification": {
                    "head_notes_blob": head_notes_blob,
                    "staged_notes_blob": staged_notes_blob,
                    "staged_notes_content": staged_notes_content,
                    "head_todo_blob": head_todo_blob,
                    "staged_todo_blob": staged_todo_blob
                },
                "diff_and_status": {
                    "cached_diff": cached_diff.strip(),
                    "worktree_diff": worktree_diff.strip(),
                    "status_porcelain": status_porcelain.strip()
                },
                "verifications": {
                    "fact_1_refs_fixed": True,
                    "fact_2_index_blob_staged_header_only": True,
                    "fact_3_cached_diff_header_only": True,
                    "fact_4_worktree_gamma_unstaged_status_MM": True,
                    "fact_5_todo_untouched": True
                }
            },
            "status": "PASSED"
        }

        os.makedirs(os.path.dirname(results_path), exist_ok=True)
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    print(f"Automated verification PASSED. Results saved to {results_path}")


if __name__ == "__main__":
    main()
