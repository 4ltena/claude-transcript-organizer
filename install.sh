#!/usr/bin/env sh
# install.sh — make tsorg / tstat / tsdel available on macOS / Linux.
#
# Symlinks the bin/ wrappers into a directory on PATH (default ~/.local/bin),
# overriding via TSORG_BIN_DIR. Idempotent. Pass --uninstall (-u) to remove.
set -eu

repo="$(cd "$(dirname "$0")" && pwd)"
target="${TSORG_BIN_DIR:-$HOME/.local/bin}"
cmds="tsorg tstat tsdel"

chmod +x "$repo/bin/tsorg" "$repo/bin/tstat" "$repo/bin/tsdel" 2>/dev/null || true

if [ "${1:-}" = "--uninstall" ] || [ "${1:-}" = "-u" ]; then
    for c in $cmds; do
        if [ -L "$target/$c" ]; then
            rm -f "$target/$c"
            echo "removed $target/$c"
        fi
    done
    exit 0
fi

mkdir -p "$target"
for c in $cmds; do
    ln -sf "$repo/bin/$c" "$target/$c"
    echo "linked $target/$c -> $repo/bin/$c"
done

case ":$PATH:" in
    *":$target:"*) : ;;
    *) echo "note: $target is not on PATH. Add this to your shell rc:"
       echo "      export PATH=\"\$PATH:$target\"" ;;
esac

command -v python3 >/dev/null 2>&1 || echo "warning: python3 not found; install Python 3.9+"
echo "done. try: tsorg --dry-run"
