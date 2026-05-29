#!/bin/sh
# Optional LOCAL commit hook (not Cursor Cloud).
# Cursor Cloud Automations fire on git PUSH, not local commit.
#
# Install (once per clone):
#   cp .cursor/automations/review-on-local-commit.hook.example.sh .git/hooks/post-commit
#   chmod +x .git/hooks/post-commit
#
# Requires Cursor CLI in PATH: https://cursor.com/docs/cli
# Adjust branch/repo as needed.

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"

cursor agent run --prompt "$(cat <<'EOF'
Run /review-loop verify on Neon. Update docs/review_loop_state.md.
If tests fail, fix ONE failing test root cause using /developer (minimal diff, one commit), then stop.
Do not refactor unrelated code.
EOF
)" 2>/dev/null &

exit 0
