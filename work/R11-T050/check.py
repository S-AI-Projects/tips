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

    # Create Commit D on topic
    run_git(['checkout', 'topic'], repo_dir, env)
    with open(os.path.join(repo_dir, 'feature.txt'), 'w') as f:
        f.write('feat\n')
    run_git(['add', 'feature.txt'], repo_dir, env)
    run_git(['commit', '-m', 'Commit D'], repo_dir, env)
    commit_d = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()

    return commit_a, commit_b, commit_c, commit_d

def verify_in_dir(tmp_root):
    env = os.environ.copy()
    fake_home = os.path.join(tmp_root, 'fake_home')
    os.makedirs(fake_home, exist_ok=True)
    env['HOME'] = fake_home
    env['GIT_CONFIG_NOSYSTEM'] = '1'

    repo_dir = os.path.join(tmp_root, 'repo')
    os.makedirs(repo_dir, exist_ok=True)
    commit_a, commit_b, commit_c, commit_d = setup_repo(repo_dir, env)

    # Command anchor: git cherry -v main
    cherry_out = run_git(['cherry', '-v', 'main'], repo_dir, env).stdout.strip()

    # Assertions
    # Fact 1: Output indicates Commit D is unmerged with '+' prefix
    assert cherry_out.startswith(f"+ {commit_d}"), f"Expected cherry output starting with '+ {commit_d}', got: {cherry_out}"
    assert "Commit D" in cherry_out

    # Fact 2: Comparing in reverse (main against topic) shows Commit C
    cherry_rev = run_git(['cherry', '-v', 'topic', 'main'], repo_dir, env).stdout.strip()
    assert cherry_rev.startswith(f"+ {commit_c}"), f"Expected cherry output starting with '+ {commit_c}', got: {cherry_rev}"

    # Fact 3: HEAD and branch refs are completely unchanged
    head = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()
    topic = run_git(['rev-parse', 'refs/heads/topic'], repo_dir, env).stdout.strip()
    main_ref = run_git(['rev-parse', 'refs/heads/main'], repo_dir, env).stdout.strip()
    assert head == commit_d
    assert topic == commit_d
    assert main_ref == commit_c

    # Fact 4: Working tree and index are clean
    status = run_git(['status', '--porcelain'], repo_dir, env).stdout.strip()
    assert status == "", f"Working tree not clean: {status}"

    return {
        "commit_c": commit_c,
        "commit_d": commit_d,
        "cherry_out": cherry_out,
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
            "upstream_branch": "main (Commits A, B, C)",
            "feature_branch": "topic (Commits A, B, D)",
            "command": "git cherry -v main"
        },
        "expected_results": {
            "fact_1": "git cherry -v main outputs '+ <Commit_D_SHA> Commit D'",
            "fact_2": "Reverse cherry comparison outputs '+ <Commit_C_SHA> Commit C'",
            "fact_3": "HEAD, refs/heads/topic, and refs/heads/main are completely unchanged",
            "fact_4": "Working tree and index remain completely clean"
        },
        "actual_results": res1,
        "status": "PASSED",
        "reproducibility": "PASSED across two independent runs"
    }

    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print("Task R11-T050 automated check PASSED.")

if __name__ == '__main__':
    main()
