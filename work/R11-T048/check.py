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

    # Checkout topic and create Commit D
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

    # Command anchor: git rebase --onto <new_base> <old_base>
    run_git(['rebase', '--onto', 'main', commit_b, 'topic'], repo_dir, env)
    rebased_topic_head = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()

    # Assertions
    # Fact 1: Rebased commit parent is Commit C (new base)
    parent_of_rebased = run_git(['rev-parse', 'HEAD^'], repo_dir, env).stdout.strip()
    assert parent_of_rebased == commit_c, f"Expected parent {commit_c}, got {parent_of_rebased}"

    # Fact 2: Feature changes from Commit D are preserved
    assert os.path.exists(os.path.join(repo_dir, 'feature.txt')), "feature.txt not in rebased topic"
    with open(os.path.join(repo_dir, 'feature.txt')) as f:
        assert f.read() == 'feat\n'

    # Fact 3: Changes from Commit C (todo.txt) are now present in topic
    assert os.path.exists(os.path.join(repo_dir, 'todo.txt')), "todo.txt missing after rebase onto main"

    # Fact 4: main branch ref remained unchanged at Commit C
    main_ref = run_git(['rev-parse', 'refs/heads/main'], repo_dir, env).stdout.strip()
    assert main_ref == commit_c, f"main ref moved during topic rebase: {main_ref}"

    return {
        "commit_c": commit_c,
        "commit_d": commit_d,
        "rebased_topic_head": rebased_topic_head,
        "parent_of_rebased": parent_of_rebased
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
            "command": "git rebase --onto main Commit_B topic",
            "old_base": "Commit B",
            "new_base": "main (Commit C)"
        },
        "expected_results": {
            "fact_1": "Parent of rebased topic commit is Commit C",
            "fact_2": "Commit D changes (feature.txt) preserved on topic branch",
            "fact_3": "todo.txt from Commit C is now present in working tree",
            "fact_4": "refs/heads/main remains unchanged at Commit C"
        },
        "actual_results": res1,
        "status": "PASSED",
        "reproducibility": "PASSED across two independent runs"
    }

    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print("Task R11-T048 automated check PASSED.")

if __name__ == '__main__':
    main()
