#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile

def run_git(args, cwd, env, check=True):
    return subprocess.run(['git'] + args, cwd=cwd, env=env, text=True, capture_output=True, check=check)

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

    # Start interactive rebase with editor stopping at edit
    # We set GIT_SEQUENCE_EDITOR to change 'pick' to 'edit' for the last commit
    seq_editor = os.path.join(tmp_root, 'seq_editor.sh')
    with open(seq_editor, 'w') as f:
        f.write('#!/bin/sh\nsed -i "" "s/^pick/edit/" "$1" 2>/dev/null || sed -i "s/^pick/edit/" "$1"\n')
    os.chmod(seq_editor, 0o755)

    rebase_env = env.copy()
    rebase_env['GIT_SEQUENCE_EDITOR'] = seq_editor

    # Run rebase
    run_git(['rebase', '-i', 'HEAD~2'], repo_dir, rebase_env)

    # Verify rebase is in progress
    git_dir = run_git(['rev-parse', '--git-dir'], repo_dir, env).stdout.strip()
    rebase_merge_dir = os.path.join(repo_dir, git_dir, 'rebase-merge')
    assert os.path.exists(rebase_merge_dir), "rebase-merge directory not created during rebase"

    # Now execute recovery: git rebase --abort
    run_git(['rebase', '--abort'], repo_dir, env)

    # Assertions
    # Fact 1: HEAD ref after abort exactly matches Commit C
    head_after_abort = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()
    assert head_after_abort == commit_c, f"HEAD after abort {head_after_abort} != initial {commit_c}"

    # Fact 2: Transient rebase state cleaned up
    assert not os.path.exists(rebase_merge_dir), "rebase-merge directory was not cleaned up after abort"

    # Fact 3: Working tree and staging area are clean
    status = run_git(['status', '--porcelain'], repo_dir, env).stdout.strip()
    assert status == "", f"Working tree not clean after rebase abort: {status}"

    # Fact 4: Reflog records rebase abort / restoration
    reflog_top = run_git(['reflog', '-n', '1'], repo_dir, env).stdout.strip()
    assert "rebase" in reflog_top.lower(), f"Reflog did not capture rebase action: {reflog_top}"

    return {
        "initial_head": commit_c,
        "head_after_abort": head_after_abort,
        "reflog_entry": reflog_top,
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
            "initial_commits": ["A", "B", "C"],
            "command": "git rebase --interactive HEAD~2",
            "recovery_command": "git rebase --abort"
        },
        "expected_results": {
            "fact_1": "HEAD after abort resolves to exact pre-rebase Commit C SHA",
            "fact_2": ".git/rebase-merge state directory is fully removed",
            "fact_3": "Working tree and staging index are clean",
            "fact_4": "Reflog records rebase recovery transition"
        },
        "actual_results": res1,
        "status": "PASSED",
        "reproducibility": "PASSED across two independent runs"
    }

    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print("Task R11-T043 automated check PASSED.")

if __name__ == '__main__':
    main()
