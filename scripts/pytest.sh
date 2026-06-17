#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly PYTEST_TIMEOUT_SECONDS="5"

cd "${REPO_ROOT}"

export QT_QPA_PLATFORM="offscreen"
export PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE="1"

printf 'Running pytest with enforced %ss timeout\n' "${PYTEST_TIMEOUT_SECONDS}"
printf 'Command: uv run pytest'
for arg in "$@"; do
    printf ' %q' "$arg"
done
printf '\n'

exec timeout --foreground --signal=TERM --kill-after=2s "${PYTEST_TIMEOUT_SECONDS}s" \
    uv run pytest "$@"
