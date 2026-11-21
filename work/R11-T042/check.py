#!/usr/bin/env python3
import os, subprocess, sys, tempfile, shutil

def run(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        print(f"Command failed: {cmd}\nOutput:\n{result.stdout}")
        sys.exit(1)
    return result.stdout.strip()

# Create temporary directory
temp_dir = tempfile.mkdtemp()
try:
    # init repo
    run('git init', cwd=temp_dir)
    # configure user
    run('git config user.email "test@example.com"', cwd=temp_dir)
    run('git config user.name "Test User"', cwd=temp_dir)
    # create initial commit A
    with open(os.path.join(temp_dir, 'file.txt'), 'w') as f:
        f.write('A')
    run('git add file.txt', cwd=temp_dir)
    run('git commit -m A', cwd=temp_dir)
    # commit B
    with open(os.path.join(temp_dir, 'file.txt'), 'a') as f:
        f.write('\nB')
    run('git add file.txt', cwd=temp_dir)
    run('git commit -m B', cwd=temp_dir)
    # get SHA of B
    shaB = run('git rev-parse HEAD', cwd=temp_dir)
    # create branch topic at B
    run('git checkout -b topic', cwd=temp_dir)
    # commit C on main
    run('git checkout master', cwd=temp_dir)
    with open(os.path.join(temp_dir, 'file.txt'), 'a') as f:
        f.write('\nC')
    run('git add file.txt', cwd=temp_dir)
    run('git commit -m C', cwd=temp_dir)
    # get merge-base of master and topic
    merge_base = run('git merge-base master topic', cwd=temp_dir)
    # Validate merge base equals B
    if merge_base != shaB:
        print(f"Merge base {merge_base} does not match expected {shaB}")
        sys.exit(1)
    # Ensure working tree clean
    status = run('git status --porcelain', cwd=temp_dir)
    if status:
        print('Working tree not clean')
        sys.exit(1)
    # Verify refs unchanged (compare hashes)
    master_sha = run('git rev-parse master', cwd=temp_dir)
    topic_sha = run('git rev-parse topic', cwd=temp_dir)
    # master should be commit C, topic should be B
    if master_sha == topic_sha:
        print('Master and topic point to same commit unexpectedly')
        sys.exit(1)
    print('All checks passed')
finally:
    shutil.rmtree(temp_dir)

