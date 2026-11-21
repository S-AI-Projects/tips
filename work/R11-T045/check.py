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

    # Add directory and file with spaces and UTF-8 characters: "release notes/v1.0.txt"
    rel_dir = os.path.join(repo_dir, 'release notes')
    os.makedirs(rel_dir, exist_ok=True)
    file_path = os.path.join(rel_dir, 'v1.0.txt')
    utf8_content = "Notas de la versión 1.0 — Initial Release 🚀\n"
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(utf8_content)

    # Use literal path argument without shell globbing
    run_git(['add', 'release notes/v1.0.txt'], repo_dir, env)
    run_git(['commit', '-m', 'Add release notes v1.0'], repo_dir, env)
    commit_before_amend = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()

    # Command anchor: git commit --amend --author=...
    new_author = 'Updated Author <updated@example.invalid>'
    run_git(['commit', '--amend', f'--author={new_author}', '--no-edit'], repo_dir, env)
    commit_after_amend = run_git(['rev-parse', 'HEAD'], repo_dir, env).stdout.strip()

    # Assertions
    # Fact 1: Author metadata successfully amended
    author_name = run_git(['log', '-1', '--format=%an'], repo_dir, env).stdout.strip()
    author_email = run_git(['log', '-1', '--format=%ae'], repo_dir, env).stdout.strip()
    assert author_name == 'Updated Author', f"Author name mismatch: {author_name}"
    assert author_email == 'updated@example.invalid', f"Author email mismatch: {author_email}"

    # Fact 2: Quoted path with spaces and non-ASCII characters is preserved exactly in tree
    tracked_files = run_git(['ls-tree', '-r', '--name-only', 'HEAD'], repo_dir, env).stdout.splitlines()
    assert 'release notes/v1.0.txt' in tracked_files, f"Path not found in ls-tree: {tracked_files}"

    # Fact 3: Exact file content is preserved
    show_content = run_git(['show', 'HEAD:release notes/v1.0.txt'], repo_dir, env).stdout
    assert show_content == utf8_content, "Amended commit altered file contents"

    # Fact 4: Commit SHA replaced while parent is unchanged
    assert commit_after_amend != commit_before_amend, "Commit SHA did not change after amend"
    parent = run_git(['rev-parse', 'HEAD^'], repo_dir, env).stdout.strip()
    assert parent == commit_c, f"Parent commit changed: expected {commit_c}, got {parent}"

    return {
        "commit_before_amend": commit_before_amend,
        "commit_after_amend": commit_after_amend,
        "author_name": author_name,
        "author_email": author_email,
        "tracked_files": tracked_files
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
            "file_with_spaces_and_utf8": "release notes/v1.0.txt",
            "amended_author": "Updated Author <updated@example.invalid>"
        },
        "expected_results": {
            "fact_1": "Commit author is amended to Updated Author <updated@example.invalid>",
            "fact_2": "Literal path 'release notes/v1.0.txt' is retained in git tree without glob expansion",
            "fact_3": "UTF-8 file content is preserved bit-for-bit",
            "fact_4": "Commit SHA changes while parent remains Commit C"
        },
        "actual_results": res1,
        "status": "PASSED",
        "reproducibility": "PASSED across two independent runs"
    }

    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print("Task R11-T045 automated check PASSED.")

if __name__ == '__main__':
    main()
