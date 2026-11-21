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

    # Commit A
    with open(os.path.join(repo_dir, 'notes.txt'), 'w') as f:
        f.write('alpha\n')
    run_git(['add', 'notes.txt'], repo_dir, env)
    run_git(['commit', '-m', 'Commit A'], repo_dir, env)
    commit_a = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()

    # Commit B
    with open(os.path.join(repo_dir, 'notes.txt'), 'a') as f:
        f.write('beta\n')
    run_git(['add', 'notes.txt'], repo_dir, env)
    run_git(['commit', '-m', 'Commit B'], repo_dir, env)
    commit_b = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()

    # Branch topic at B
    run_git(['branch', 'topic', commit_b], repo_dir, env)

    # Commit C
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

    # Modify notes.txt and create untracked patch.txt
    with open(os.path.join(repo_dir, 'notes.txt'), 'a') as f:
        f.write('work in progress\n')
    with open(os.path.join(repo_dir, 'patch.txt'), 'w') as f:
        f.write('new patch\n')

    # Run git stash push -u -m
    stash_msg = "WIP: save notes and patch"
    run_git(['stash', 'push', '-u', '-m', stash_msg], repo_dir, env)

    # Command anchor: git stash list
    stash_list = run_git(['stash', 'list'], repo_dir, env).stdout.strip()

    # Assertions
    # Fact 1: Stash list contains the message
    assert stash_msg in stash_list, f"Stash list does not contain '{stash_msg}': {stash_list}"
    assert "stash@{0}" in stash_list, f"Stash entry format incorrect: {stash_list}"

    # Fact 2: Refs main and topic are unchanged
    head_sha = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()
    topic_sha = run_git(['rev-parse', 'refs/heads/topic'], repo_dir, env).stdout.strip()
    assert head_sha == commit_c, f"HEAD moved! Expected {commit_c}, got {head_sha}"
    assert topic_sha == commit_b, f"topic moved! Expected {commit_b}, got {topic_sha}"

    # Fact 3: Working tree is restored to clean state
    status = run_git(['status', '--porcelain'], repo_dir, env).stdout.strip()
    assert status == "", f"Working tree not clean after stash: {status}"
    assert not os.path.exists(os.path.join(repo_dir, 'patch.txt')), "Untracked file patch.txt was not stashed"

    # Fact 4: refs/stash ref exists and resolves
    stash_sha = run_git(['rev-parse', 'refs/stash'], repo_dir, env).stdout.strip()
    assert len(stash_sha) == 40, f"Invalid stash SHA: {stash_sha}"

    return {
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "stash_sha": stash_sha,
        "stash_list": stash_list,
        "status": status
    }

def main():
    # Run in two separate temporary directories to prove reproducibility
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
            "commits": ["Commit A", "Commit B", "Commit C"],
            "stash_message": "WIP: save notes and patch"
        },
        "expected_results": {
            "fact_1": "git stash list outputs stash@{0}: On main: WIP: save notes and patch",
            "fact_2": "refs/heads/main == Commit C and refs/heads/topic == Commit B",
            "fact_3": "Working tree is clean and untracked patch.txt is stashed",
            "fact_4": "refs/stash resolves to valid commit SHA"
        },
        "actual_results": res1,
        "status": "PASSED",
        "reproducibility": "PASSED across two independent runs"
    }

    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print("Task R11-T041 automated check PASSED.")

if __name__ == '__main__':
    main()
