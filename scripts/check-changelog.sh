#!/bin/bash
# Warn (do not block) if Python source files were staged without CHANGELOG.md.
STAGED=$(git diff --cached --name-only)

if echo "$STAGED" | grep -qE "^(src/ai_launcher|scripts)/.*\.py$"; then
    if ! echo "$STAGED" | grep -q "^CHANGELOG.md$"; then
        echo ""
        echo "⚠️  CHANGELOG.md not updated — did you forget?"
        echo "   Python files in src/ or scripts/ were changed."
        echo "   Consider adding a ## [X.Y.Z] entry. See docs/releasing.md."
        echo ""
    fi
fi

exit 0
