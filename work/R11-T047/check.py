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

    # Configure the alias locally
    alias_cmd = '!f() { git reset --hard $(git rev-parse --abbrev-ref HEAD)@{${1-1}}; }; f'
    run_git(['config', 'alias.undo', alias_cmd], repo_dir, env)

    # Test 1: Successful undo from Commit C back to Commit B
    run_git(['undo'], repo_dir, env)
    head_after_undo = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()
    assert head_after_undo == commit_b, f"Undo did not restore Commit B: {head_after_undo}"

    # Test 2: Trigger known failure mode: requesting out-of-bounds reflog entry
    fail_res = run_git(['undo', '99'], repo_dir, env, check=False)
    assert fail_res.returncode != 0, f"Expected non-zero exit code on missing reflog entry, got {fail_res.returncode}"
    assert "fatal:" in fail_res.stderr.lower() or "log for" in fail_res.stderr.lower() or "fatal" in fail_res.stdout.lower()

    # Fact 3: Configure safe alias and verify error handling
    safe_alias = '!f() { target=$(git rev-parse --abbrev-ref HEAD)@{${1-1}}; git rev-parse -q --verify "$target" >/dev/null || { echo "fatal: target reflog entry $target does not exist" >&2; exit 1; }; git reset --hard "$target"; }; f'
    run_git(['config', 'alias.undo', safe_alias], repo_dir, env)
    safe_fail = run_git(['undo', '99'], repo_dir, env, check=False)
    assert safe_fail.returncode == 1
    assert "fatal: target reflog entry" in safe_fail.stderr

    return {
        "commit_c": commit_c,
        "head_after_undo": head_after_undo,
        "failure_exit_code": fail_res.returncode,
        "failure_stderr": fail_res.stderr.strip()
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
            "alias": "git undo",
            "failure_trigger": "git undo 99 (requesting nonexistent reflog entry)"
        },
        "expected_results": {
            "fact_1": "git undo correctly resets branch HEAD to previous reflog entry",
            "fact_2": "Invoking git undo with missing reflog index exits non-zero and captures fatal error",
            "fact_3": "Safe alias validates target ref before attempting destructive reset"
        },
        "actual_results": res1,
        "status": "PASSED",
        "reproducibility": "PASSED across two independent runs"
    }

    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print("Task R11-T047 automated check PASSED.")

if __name__ == '__main__':
    main()
