import os
import subprocess
import sys
import tempfile
from pathlib import Path

def git(args, repo, env):
    return subprocess.run(
        ["git"] + args,
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()

def main():
    omit = "--omit-decisive-command" in sys.argv

    with tempfile.TemporaryDirectory() as temp:
        repo = Path(temp) / "repo"
        home = Path(temp) / "home"
        repo.mkdir()
        home.mkdir()

        env = os.environ.copy()
        env["HOME"] = str(home)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = str(home / ".gitconfig")

        git(["init", "-b", "main"], repo, env)
        git(["config", "user.name", "Course Student"], repo, env)
        git(["config", "user.email", "student@example.invalid"], repo, env)

        (repo / "notes.txt").write_text("alpha\n")
        git(["add", "notes.txt"], repo, env)
        git(["commit", "-m", "A"], repo, env)

        (repo / "notes.txt").write_text("alpha\nbeta\n")
        git(["add", "notes.txt"], repo, env)
        git(["commit", "-m", "B"], repo, env)
        commit_b = git(["rev-parse", "HEAD"], repo, env)

        git(["branch", "topic", commit_b], repo, env)

        (repo / "todo.txt").write_text("one\n")
        git(["add", "todo.txt"], repo, env)
        git(["commit", "-m", "C"], repo, env)
        commit_c = git(["rev-parse", "HEAD"], repo, env)

        if not omit:
            git(["config", "--global", "core.editor", "$EDITOR"], repo, env)

        assert git(["branch", "--show-current"], repo, env) == "main"
        assert git(["rev-parse", "HEAD"], repo, env) == commit_c
        assert git(["rev-parse", "topic"], repo, env) == commit_b
        assert (repo / "notes.txt").read_text() == "alpha\nbeta\n"
        assert (repo / "todo.txt").read_text() == "one\n"
        assert git(["show", "topic:notes.txt"], repo, env) == "alpha\nbeta"

        result = subprocess.run(
            ["git", "cat-file", "-e", "topic:todo.txt"],
            cwd=repo, env=env, capture_output=True
        )
        assert result.returncode != 0

        assert git(
            ["config", "--global", "--get", "core.editor"],
            repo, env
        ) == "$EDITOR"

        print("PASS: All custom editor assertions")

if __name__ == "__main__":
    main()
