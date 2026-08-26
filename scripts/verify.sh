#!/usr/bin/env bash
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
cd "$root"
git diff --check
test -s README.md
test -s LICENSE
while IFS= read -r -d '' link; do echo "symlink is not allowed in reusable resources: $link" >&2; exit 1; done < <(find . -path ./.git -prune -o -type l -print0)
python3 - <<'PY'
from pathlib import Path
required=[Path('themes/gethomepage/hypershell-neon/custom.css'),Path('themes/gethomepage/hypershell-neon/settings.example.yaml'),Path('themes/gethomepage/hypershell-neon/README.md')]
for p in required:
    assert p.is_file() and p.stat().st_size > 0, p
css=required[0].read_text(encoding='utf-8')
assert '{' in css and '}' in css
settings=required[1].read_text(encoding='utf-8')
assert ':' in settings
PY
