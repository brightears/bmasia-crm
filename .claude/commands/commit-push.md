# Commit and Push Changes

Commit all staged changes and push to GitHub.

## Usage
```
/commit-push [description of changes]
```

Example:
- `/commit-push Fix email template routing`
- `/commit-push Add Valentine's Day campaign`

## Steps

### 1. Pre-flight Checks
```bash
git status
git diff --stat
```
- Show what files will be committed
- If no changes, report "Nothing to commit"

### 2. Stage Changes
Ask user which files to stage:
- All changes: `git add .`
- Specific files: `git add [files]`

### 3. Create Commit
Generate commit message following project conventions:
```bash
git commit -m "$(cat <<'EOF'
[Type]: [Brief description]

[Detailed description if needed]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

Types:
- Feature: New functionality
- Fix: Bug fix
- Docs: Documentation
- Refactor: Code restructuring
- Test: Adding tests

### 4. Push to GitHub
```bash
git push origin main
```

### 5. Report
- Show commit hash
- Show files changed
- Provide link to GitHub commit
