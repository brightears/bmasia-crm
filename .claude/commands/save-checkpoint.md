# Save Session Checkpoint

Create a session checkpoint document to preserve context before auto-compact.

## Usage
```
/save-checkpoint [topic]
```

Example:
- `/save-checkpoint email-automation`
- `/save-checkpoint contract-management`

## Checkpoint Contents

Create file: `SESSION_CHECKPOINT_{DATE}_{TOPIC}.md`

### Required Sections

1. **Summary** - Brief overview of what was accomplished
2. **Completed Work** - List of completed tasks with details
3. **Files Modified** - Table of changed files
4. **Technical Details** - Important implementation notes
5. **Git Commits** - Recent commit hashes
6. **Production URLs** - Links to deployed services
7. **Next Steps** - What to do next session
8. **User Questions** - Any pending questions answered

### Template
```markdown
# Session Checkpoint: {Topic}
**Date**: {Today's Date}
**Status**: {Complete/In Progress}

---

## Summary
{Brief overview}

---

## Completed Work
- Task 1
- Task 2

---

## Files Modified
| File | Changes |
|------|---------|
| file.py | Description |

---

## Git Commits
```
{commit_hash} {message}
```

---

## Production URLs
- Backend: https://bmasia-crm.onrender.com
- Frontend: https://bmasia-crm-frontend.onrender.com

---

## Next Steps
1. Step 1
2. Step 2
```

## File Location
Save to project root: `/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM/`
