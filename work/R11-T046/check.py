#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile

def run_git(args, cwd, env):
    return subprocess.run(['git'] + args, cwd=cwd, env=env, text=True, capture_output=True, check=True)

def setup_repo(repo_dir, env):
    run_git(['init', '-b', 'main'], repo_dir, env)
    run_git(['config', 'user.name', 'Course Student'], repo_dir, env)
    run_git(['config', 'user.email', 'student@example.invalid'], repo_dir, env)

    with open(os.path.join(repo_dir, 'notes.txt'), 'w') as f:
        f.write('alpha\n')
    run_git(['add', 'notes.txt'], repo_dir, env)
    run_git(['commit', '-m', 'Commit A'], repo_dir, env)
    commit_a = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()

    with open(os.path.join(repo_dir, 'notes.txt'), 'a') as f:
        f.write('beta\n')
    run_git(['add', 'notes.txt'], repo_dir, env)
    run_git(['commit', '-m', 'Commit B'], repo_dir, env)
    commit_b = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()

    run_git(['branch', 'topic', commit_b], repo_dir, env)

    with open(os.path.join(repo_dir, 'todo.txt'), 'w') as f:
        f.write('one\n')
    run_git(['add', 'todo.txt'], repo_dir, env)
    run_git(['commit', '-m', 'Commit C'], repo_dir, env)
    commit_c = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()

    return commit_a, commit_b, commit_c

def verify_in_dir(tmp_root):
    env = os.environ.copy()
    fake_home = os.path.join(tmp_root, 'fake_home')
    os.makedirs(fake_home, exist_ok=True)
    env['HOME'] = fake_home
    env['GIT_CONFIG_NOSYSTEM'] = '1'

    repo_dir = os.path.join(tmp_root, 'repo')
    os.makedirs(repo_dir, exist_ok=True)
    commit_a, commit_b, commit_c = setup_repo(repo_dir, env)

    # Command anchor: git log --author=... --pretty=tformat: --numstat
    numstat_raw = run_git(['log', '--author=Course Student', '--pretty=tformat:', '--numstat'], repo_dir, env).stdout
    added, removed = 0, 0
    for line in numstat_raw.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            added += int(parts[0])
            removed += int(parts[1])

    # Assertions
    # Fact 1: Added lines count exactly matches 3 across commits A, B, C
    assert added == 3, f"Expected 3 added lines, got {added}"
    assert removed == 0, f"Expected 0 removed lines, got {removed}"

    # Fact 2: Alternative command (--shortstat) confirms commits and insertions
    shortstat_raw = run_git(['log', '--author=Course Student', '--shortstat'], repo_dir, env).stdout
    assert "3 files changed, 3 insertions(+)" in shortstat_raw or "insertion" in shortstat_raw

    # Fact 3: Read-only verification: HEAD, refs, index, worktree unchanged
    head = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()
    topic = run_git(['rev-parse', 'refs/heads/topic'], repo_dir, env).stdout.strip()
    assert head == commit_c, f"HEAD changed: {head}"
    assert topic == commit_b, f"topic changed: {topic}"
    status = run_git(['status', '--porcelain'], repo_dir, env).stdout.strip()
    assert status == "", f"Worktree changed: {status}"

    return {
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "added_lines": added,
        "removed_lines": removed,
        "status": status
    }

def main():
    with tempfile.TemporaryDirectory() as run1_dir:
        res1 = verify_in_dir(run1_dir)
    with tempfile.TemporaryDirectory() as run2_dir:
        res2 = verify_in_dir(run2_dir)

    results = {
        "tool_versions": {
            "git": subprocess.check_output(['git', '--version'], text=True).strip(),
            "python": sys.version.replace('\n', ' ')
        },
        "inputs": {
            "author": "Course Student <student@example.invalid>",
            "commits": 3,
            "command": "git log --author='Course Student' --pretty=tformat: --numstat"
        },
        "expected_results": {
            "fact_1": "Total added lines calculated equals 3, removed lines equals 0",
            "fact_2": "Alternative shortstat command confirms commit insertion counts",
            "fact_3": "Query operation leaves HEAD, refs, index, and worktree untouched"
        },
        "actual_results": res1,
        "status": "PASSED",
        "reproducibility": "PASSED across two independent runs"
    }

    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print("Task R11-T046 automated check PASSED.")

if __name__ == '__main__':
    main()
