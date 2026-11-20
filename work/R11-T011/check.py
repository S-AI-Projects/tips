#!/usr/bin/env python3
"""
Automated verification script for task R11-T011:
'Get first commit in a branch (from master)'

Verifies:
1. Exact file contents across commits A, B, and C.
2. Branch ref pointers: 'main' points to Commit B, 'topic' points to Commit C.
3. Commit range: 'main..' contains only Commit C.
4. Log outputs:
   - git log --oneline main.. | tail -1
   - git log --reverse main.. | head -6
   - Master-based equivalents:
     - git log --oneline master.. | tail -1
     - git log --reverse master.. | head -6
5. Clean index and working tree.
6. Execution across two separate temporary repositories to ensure consistency.
7. Use of dynamic Git object IDs and return code verification for all subprocess calls.
"""

import os
import sys
import subprocess
import tempfile


def run_cmd(cmd: str, cwd: str) -> str:
    """Executes a shell command via subprocess and verifies return code is zero."""
    res = subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True
    )
    if res.returncode != 0:
        print(f"Error: command failed with return code {res.returncode}: {cmd}", file=sys.stderr)
        print(f"STDOUT: {res.stdout}", file=sys.stderr)
        print(f"STDERR: {res.stderr}", file=sys.stderr)
        sys.exit(res.returncode if res.returncode != 0 else 1)
    return res.stdout


def run_scenario(scenario_id: int) -> dict:
    """Runs the complete scenario in an isolated temporary repository."""
    print(f"=== Running Scenario {scenario_id} ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: Initialize branch main and set author configuration
        run_cmd("git init -b main", tmpdir)
        run_cmd("git config user.name \"Course Student\"", tmpdir)
        run_cmd("git config user.email \"student@example.invalid\"", tmpdir)
        
        # Step 2: Commit A: create notes.txt containing alpha\n
        notes_file = os.path.join(tmpdir, "notes.txt")
        with open(notes_file, "w", encoding="utf-8") as f:
            f.write("alpha\n")
        
        with open(notes_file, "r", encoding="utf-8") as f:
            notes_a_content = f.read()
        if notes_a_content != "alpha\n":
            print(f"Assertion failed: Commit A notes.txt content '{notes_a_content}' != 'alpha\\n'", file=sys.stderr)
            sys.exit(1)
            
        run_cmd("git add notes.txt", tmpdir)
        run_cmd("git commit -m \"Commit A\"", tmpdir)
        commit_a_id = run_cmd("git rev-parse HEAD", tmpdir).strip()
        
        # Step 3: Commit B: append beta\n
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write("beta\n")
            
        with open(notes_file, "r", encoding="utf-8") as f:
            notes_b_content = f.read()
        if notes_b_content != "alpha\nbeta\n":
            print(f"Assertion failed: Commit B notes.txt content '{notes_b_content}' != 'alpha\\nbeta\\n'", file=sys.stderr)
            sys.exit(1)
            
        run_cmd("git add notes.txt", tmpdir)
        run_cmd("git commit -m \"Commit B\"", tmpdir)
        commit_b_id = run_cmd("git rev-parse HEAD", tmpdir).strip()
        
        # Step 4: Create branch topic at Commit B and switch to it
        run_cmd("git branch topic", tmpdir)
        run_cmd("git checkout topic", tmpdir)
        
        # Step 5: Commit C on topic: create todo.txt containing one\n
        todo_file = os.path.join(tmpdir, "todo.txt")
        with open(todo_file, "w", encoding="utf-8") as f:
            f.write("one\n")
            
        with open(todo_file, "r", encoding="utf-8") as f:
            todo_c_content = f.read()
        if todo_c_content != "one\n":
            print(f"Assertion failed: Commit C todo.txt content '{todo_c_content}' != 'one\\n'", file=sys.stderr)
            sys.exit(1)
            
        run_cmd("git add todo.txt", tmpdir)
        run_cmd("git commit -m \"Commit C\"", tmpdir)
        commit_c_id = run_cmd("git rev-parse HEAD", tmpdir).strip()
        commit_c_short = run_cmd("git rev-parse --short HEAD", tmpdir).strip()
        
        # --- Assertions ---
        # 1. Assert exact file contents on disk
        if not os.path.exists(notes_file):
            print("Assertion failed: notes.txt missing after Commit C", file=sys.stderr)
            sys.exit(1)
        with open(notes_file, "r", encoding="utf-8") as f:
            if f.read() != "alpha\nbeta\n":
                print("Assertion failed: notes.txt content modified unexpectedly", file=sys.stderr)
                sys.exit(1)
                
        if not os.path.exists(todo_file):
            print("Assertion failed: todo.txt missing after Commit C", file=sys.stderr)
            sys.exit(1)
        with open(todo_file, "r", encoding="utf-8") as f:
            if f.read() != "one\n":
                print("Assertion failed: todo.txt content modified unexpectedly", file=sys.stderr)
                sys.exit(1)
                
        # 2. Assert main points to Commit B
        main_ref = run_cmd("git rev-parse main", tmpdir).strip()
        if main_ref != commit_b_id:
            print(f"Assertion failed: main ref '{main_ref}' != Commit B '{commit_b_id}'", file=sys.stderr)
            sys.exit(1)
            
        # 3. Assert topic points to Commit C
        topic_ref = run_cmd("git rev-parse topic", tmpdir).strip()
        if topic_ref != commit_c_id:
            print(f"Assertion failed: topic ref '{topic_ref}' != Commit C '{commit_c_id}'", file=sys.stderr)
            sys.exit(1)
            
        # 4. Assert main.. contains only Commit C
        rev_list = run_cmd("git rev-list main..", tmpdir).strip().splitlines()
        if rev_list != [commit_c_id]:
            print(f"Assertion failed: main.. commits '{rev_list}' != '{[commit_c_id]}'", file=sys.stderr)
            sys.exit(1)
            
        # 5. Assert log command outputs
        # 5a. git log --oneline main.. | tail -1
        log_oneline = run_cmd("git log --oneline main.. | tail -1", tmpdir).strip()
        expected_oneline = f"{commit_c_short} Commit C"
        if log_oneline != expected_oneline:
            print(f"Assertion failed: oneline output '{log_oneline}' != '{expected_oneline}'", file=sys.stderr)
            sys.exit(1)
            
        # 5b. git log --reverse main.. | head -6
        log_reverse = run_cmd("git log --reverse main.. | head -6", tmpdir).strip()
        if f"commit {commit_c_id}" not in log_reverse:
            print(f"Assertion failed: reverse output missing commit {commit_c_id}", file=sys.stderr)
            sys.exit(1)
        if "Author: Course Student <student@example.invalid>" not in log_reverse:
            print("Assertion failed: reverse output missing author", file=sys.stderr)
            sys.exit(1)
        if "Commit C" not in log_reverse:
            print("Assertion failed: reverse output missing commit message", file=sys.stderr)
            sys.exit(1)
            
        # 5c. Master-based equivalents
        run_cmd("git branch master main", tmpdir)
        master_rev_list = run_cmd("git rev-list master..", tmpdir).strip().splitlines()
        if master_rev_list != [commit_c_id]:
            print(f"Assertion failed: master.. commits '{master_rev_list}' != '{[commit_c_id]}'", file=sys.stderr)
            sys.exit(1)
            
        master_oneline = run_cmd("git log --oneline master.. | tail -1", tmpdir).strip()
        if master_oneline != expected_oneline:
            print(f"Assertion failed: master oneline '{master_oneline}' != '{expected_oneline}'", file=sys.stderr)
            sys.exit(1)
            
        master_reverse = run_cmd("git log --reverse master.. | head -6", tmpdir).strip()
        if f"commit {commit_c_id}" not in master_reverse:
            print(f"Assertion failed: master reverse missing commit {commit_c_id}", file=sys.stderr)
            sys.exit(1)
        if "Author: Course Student <student@example.invalid>" not in master_reverse:
            print("Assertion failed: master reverse missing author", file=sys.stderr)
            sys.exit(1)
        if "Commit C" not in master_reverse:
            print("Assertion failed: master reverse missing commit message", file=sys.stderr)
            sys.exit(1)
            
        # 6. Assert clean index and working tree
        status_porcelain = run_cmd("git status --porcelain", tmpdir).strip()
        if status_porcelain != "":
            print(f"Assertion failed: working tree not clean:\n{status_porcelain}", file=sys.stderr)
            sys.exit(1)
            
        diff_work = run_cmd("git diff", tmpdir).strip()
        if diff_work != "":
            print(f"Assertion failed: unstaged changes present:\n{diff_work}", file=sys.stderr)
            sys.exit(1)
            
        diff_cached = run_cmd("git diff --cached", tmpdir).strip()
        if diff_cached != "":
            print(f"Assertion failed: staged changes present:\n{diff_cached}", file=sys.stderr)
            sys.exit(1)
            
        print(f"Scenario {scenario_id} PASSED.")
        print(f"  Dynamic Commit A: {commit_a_id}")
        print(f"  Dynamic Commit B (main): {commit_b_id}")
        print(f"  Dynamic Commit C (topic): {commit_c_id} ({commit_c_short})")
        print(f"  Log oneline: {log_oneline}")
        print(f"  Status: clean")
        
        return {
            "commit_a": commit_a_id,
            "commit_b": commit_b_id,
            "commit_c": commit_c_id,
            "commit_c_short": commit_c_short,
            "log_oneline": log_oneline
        }


def main():
    print("Starting automated verification for R11-T011...")
    res1 = run_scenario(1)
    res2 = run_scenario(2)
    
    # Verify consistent behavior across runs
    assert res1["commit_a"] != "", "Run 1 Commit A is empty"
    assert res2["commit_a"] != "", "Run 2 Commit A is empty"
    assert res1["commit_b"] != "", "Run 1 Commit B is empty"
    assert res2["commit_b"] != "", "Run 2 Commit B is empty"
    assert res1["commit_c"] != "", "Run 1 Commit C is empty"
    assert res2["commit_c"] != "", "Run 2 Commit C is empty"
    
    print("\nConsistency verification across runs:")
    print(f"Run 1 topic commit: {res1['commit_c']}")
    print(f"Run 2 topic commit: {res2['commit_c']}")
    print("Both scenarios completed successfully with clean state and expected outputs.")
    print("ALL CHECKS PASSED.")
    sys.exit(0)


if __name__ == "__main__":
    main()
