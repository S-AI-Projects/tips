# Stashing

## Saving current state of tracked files without committing
```sh
git stash
```
**Alternatives:**
```sh
git stash push
```

---

## Saving current state of unstaged changes to tracked files
```sh
git stash -k
```
**Alternatives:**
```sh
git stash --keep-index
```
```sh
git stash push --keep-index
```

---

## Saving current state including untracked files
```sh
git stash -u
```
**Alternatives:**
```sh
git stash push -u
```
```sh
git stash push --include-untracked
```

---

## Saving current state with message
```sh
git stash push -m <message>
```
**Alternatives:**
```sh
git stash push --message <message>
```

---

## Saving current state of all files (ignored, untracked, and tracked)
```sh
git stash -a
```
**Alternatives:**
```sh
git stash --all
```
```sh
git stash push --all
```

---

## Show list of all saved stashes
```sh
git stash list
```

**Example:**

```sh
# Create a temporary repository
mkdir -p /tmp/example-repo && cd /tmp/example-repo
git init
export GIT_AUTHOR_NAME="Course Student"
export GIT_AUTHOR_EMAIL="student@example.invalid"
export GIT_COMMITTER_NAME="Course Student"
export GIT_COMMITTER_EMAIL="student@example.invalid"

# Commit A – notes.txt with "alpha"
echo "alpha" > notes.txt
git add notes.txt
git commit -m "A: add notes alpha"

# Commit B – append "beta"
echo "beta" >> notes.txt
git add notes.txt
git commit -m "B: append beta"

# Create branch topic at B
git branch topic

# Commit C – add todo.txt
echo "one" > todo.txt
git add todo.txt
git commit -m "C: add todo"

# Make a stash to have something to list
echo "gamma" >> notes.txt
git stash push -m "test stash"

# List stashes
git stash list
```

---

## Show the contents of any stash in patch form
```sh
git stash show -p <stash@{n}>
```

---

## Apply any stash without deleting from the stashed list
```sh
git stash apply <stash@{n}>
```

---

## Apply last stashed state and delete it from stashed list
```sh
git stash pop
```
**Alternatives:**
```sh
git stash apply stash@{0} && git stash drop stash@{0}
```

---

## Delete all stored stashes
```sh
git stash clear
```
**Alternatives:**
```sh
git stash drop <stash@{n}>
```

---

