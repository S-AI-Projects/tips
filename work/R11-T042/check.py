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

    # Command anchor: git merge-base
    merge_base_out = run_git(['merge-base', 'main', 'topic'], repo_dir, env).stdout.strip()

    # Fact 1: merge-base output equals Commit B
    assert merge_base_out == commit_b, f"Expected {commit_b}, got {merge_base_out}"

    # Fact 2: Commit ancestry: B is parent of C and ancestor of topic
    parents_of_c = run_git(['rev-parse', 'main^'], repo_dir, env).stdout.strip()
    assert parents_of_c == commit_b, f"Commit B is not parent of Commit C: {parents_of_c}"

    # Fact 3: Refs remain unchanged before and after
    head_sha = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()
    topic_sha = run_git(['rev-parse', 'refs/heads/topic'], repo_dir, env).stdout.strip()
    assert head_sha == commit_c, f"HEAD changed from {commit_c} to {head_sha}"
    assert topic_sha == commit_b, f"topic changed from {commit_b} to {topic_sha}"

    # Fact 4: Index and working tree unchanged
    status = run_git(['status', '--porcelain'], repo_dir, env).stdout.strip()
    assert status == "", f"Working tree changed: {status}"

    return {
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "merge_base": merge_base_out,
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
            "branch_main": "Commit C",
            "branch_topic": "Commit B",
            "command": "git merge-base main topic"
        },
        "expected_results": {
            "fact_1": "git merge-base main topic output equals Commit B SHA",
            "fact_2": "Commit B is verified as direct parent of Commit C",
            "fact_3": "refs/heads/main, refs/heads/topic, and HEAD are completely unchanged",
            "fact_4": "Working tree and staging index remain clean"
        },
        "actual_results": res1,
        "status": "PASSED",
        "reproducibility": "PASSED across two independent runs"
    }

    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print("Task R11-T042 automated check PASSED.")

if __name__ == '__main__':
    main()
