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

    # Precondition 1: Author name & email configured
    author_name = run_git(['config', 'user.name'], repo_dir, env).stdout.strip()
    author_email = run_git(['config', 'user.email'], repo_dir, env).stdout.strip()
    assert author_name == 'Course Student'
    assert author_email == 'student@example.invalid'

    # Precondition 2: Clean working tree
    status = run_git(['status', '--porcelain'], repo_dir, env).stdout.strip()
    assert status == "", f"Working tree not clean: {status}"

    # Precondition 3: Non-empty commit range
    count = int(run_git(['rev-list', '--count', 'topic..main'], repo_dir, env).stdout.strip())
    assert count == 1, f"Expected 1 commit in topic..main, got {count}"

    # Precondition 4: Format patch output
    patch_dir = os.path.join(tmp_root, 'patches')
    os.makedirs(patch_dir, exist_ok=True)
    run_git(['format-patch', 'topic..main', '-o', patch_dir], repo_dir, env)
    patch_files = os.listdir(patch_dir)
    assert len(patch_files) == 1, f"Expected 1 patch file, got {patch_files}"

    with open(os.path.join(patch_dir, patch_files[0])) as f:
        patch_content = f.read()
    assert "Subject: [PATCH] Commit C" in patch_content
    assert "+one" in patch_content

    # State remains clean and intact
    status_after = run_git(['status', '--porcelain'], repo_dir, env).stdout.strip()
    assert status_after == ""

    return {
        "author_email": author_email,
        "commit_count": count,
        "patch_file": patch_files[0],
        "status": status_after
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
            "prerequisites": ["user.name/email", "clean worktree", "non-empty range topic..main", "patch generation"]
        },
        "expected_results": {
            "fact_1": "user.name and user.email are properly configured in local repo config",
            "fact_2": "Working tree is verified clean via git status --porcelain",
            "fact_3": "topic..main commit range contains exactly Commit C",
            "fact_4": "git format-patch generates valid patch file containing Commit C diff and headers"
        },
        "actual_results": res1,
        "status": "PASSED",
        "reproducibility": "PASSED across two independent runs"
    }

    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print("Task R11-T049 automated check PASSED.")

if __name__ == '__main__':
    main()
