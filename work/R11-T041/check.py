import os, subprocess, tempfile, textwrap, sys

def run(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print('Command failed:', cmd)
        print('stderr:', result.stderr)
        sys.exit(1)
    return result.stdout.strip()

# Create temporary repository
temp_dir = tempfile.mkdtemp()
repo_path = os.path.join(temp_dir, 'repo')
os.mkdir(repo_path)
run('git init', cwd=repo_path)
# Configure author
git_env = {
    'GIT_AUTHOR_NAME': 'Course Student',
    'GIT_AUTHOR_EMAIL': 'student@example.invalid',
    'GIT_COMMITTER_NAME': 'Course Student',
    'GIT_COMMITTER_EMAIL': 'student@example.invalid'
}
# Helper to run with env
def run_env(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, shell=True, env={**os.environ, **git_env}, capture_output=True, text=True)
    if result.returncode != 0:
        print('Command failed:', cmd)
        print('stderr:', result.stderr)
        sys.exit(1)
    return result.stdout.strip()

# Commit A – notes.txt with alpha
with open(os.path.join(repo_path, 'notes.txt'), 'w') as f:
    f.write('alpha\n')
run_env('git add notes.txt', cwd=repo_path)
run_env('git commit -m "A: add notes alpha"', cwd=repo_path)
# Commit B – append beta
with open(os.path.join(repo_path, 'notes.txt'), 'a') as f:
    f.write('beta\n')
run_env('git add notes.txt', cwd=repo_path)
run_env('git commit -m "B: append beta"', cwd=repo_path)
# Create branch topic at this point
topic_branch = 'topic'
run_env(f'git branch {topic_branch}', cwd=repo_path)
# Commit C – add todo.txt
with open(os.path.join(repo_path, 'todo.txt'), 'w') as f:
    f.write('one\n')
run_env('git add todo.txt', cwd=repo_path)
run_env('git commit -m "C: add todo"', cwd=repo_path)
# Stash something (e.g., modify notes.txt and stash)
with open(os.path.join(repo_path, 'notes.txt'), 'a') as f:
    f.write('gamma\n')
run_env('git stash push -m "test stash"', cwd=repo_path)
# Verify stash list contains our stash
def get_stash_list():
    out = run_env('git stash list', cwd=repo_path)
    return out
stash_list = get_stash_list()
assert 'test stash' in stash_list, f'Stash entry not found in list: {stash_list}'
# Ensure branch topic exists and points to commit B
def get_branch_commit(branch):
    return run_env(f'git rev-parse {branch}', cwd=repo_path)
main_B = run_env('git rev-parse HEAD~1', cwd=repo_path)  # after commit C, HEAD~1 is B
topic_commit = get_branch_commit(topic_branch)
assert topic_commit == main_B, f'Branch {topic_branch} does not point to commit B'
print('All checks passed')
