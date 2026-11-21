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

    # Create bare remote repository
    bare_remote_dir = os.path.join(tmp_root, 'bare_remote.git')
    run_git(['init', '--bare', bare_remote_dir], tmp_root, env)
    remote_url = f"file://{bare_remote_dir}"

    repo_dir = os.path.join(tmp_root, 'repo')
    os.makedirs(repo_dir, exist_ok=True)
    commit_a, commit_b, commit_c = setup_repo(repo_dir, env)

    # Checkout branch topic
    run_git(['checkout', 'topic'], repo_dir, env)
    current_branch_before = run_git(['branch', '--show-current'], repo_dir, env).stdout.strip()
    assert current_branch_before == 'topic', f"Expected branch topic, got {current_branch_before}"

    # Command anchor: git remote add
    run_git(['remote', 'add', 'origin', remote_url], repo_dir, env)

    # Assertions
    # Fact 1: Current branch remains topic
    current_branch_after = run_git(['branch', '--show-current'], repo_dir, env).stdout.strip()
    assert current_branch_after == 'topic', f"Branch changed to {current_branch_after}"

    # Fact 2: Remote configuration is recorded
    configured_url = run_git(['config', 'remote.origin.url'], repo_dir, env).stdout.strip()
    assert configured_url == remote_url, f"Remote URL mismatch: {configured_url}"

    # Fact 3: No remote-tracking refs created immediately
    remotes_list = subprocess.run(['git', 'branch', '-r'], cwd=repo_dir, env=env, text=True, capture_output=True).stdout.strip()
    assert remotes_list == "", f"Remote-tracking branches existed before push/fetch: {remotes_list}"

    # Fact 4: After pushing topic, remote tracking ref origin/topic exists while local refs match
    run_git(['push', 'origin', 'topic:topic'], repo_dir, env)
    remote_topic = run_git(['rev-parse', 'refs/remotes/origin/topic'], repo_dir, env).stdout.strip()
    assert remote_topic == commit_b, f"Remote topic SHA mismatch: {remote_topic}"

    return {
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "remote_url": remote_url,
        "current_branch": current_branch_after,
        "remote_topic_sha": remote_topic
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
            "remote_command": "git remote add origin <url>",
            "active_branch": "topic",
            "default_branch": "main"
        },
        "expected_results": {
            "fact_1": "Active branch remains topic before and after remote add",
            "fact_2": "remote.origin.url is correctly written to repo config",
            "fact_3": "No remote-tracking refs exist prior to fetch/push",
            "fact_4": "Pushing topic creates refs/remotes/origin/topic matching Commit B"
        },
        "actual_results": res1,
        "status": "PASSED",
        "reproducibility": "PASSED across two independent runs"
    }

    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print("Task R11-T044 automated check PASSED.")

if __name__ == '__main__':
    main()
