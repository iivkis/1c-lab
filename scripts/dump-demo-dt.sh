#!/usr/bin/env bash
# Dump a real tested educational infobase for submission.
set -euo pipefail
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ $# -eq 1 ]] || die "Usage: $0 EXISTING_FILE_INFOBASE_PATH"
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
db_dir="$(realpath -- "$1")"
[[ -s "$db_dir/1Cv8.1CD" ]] || die "No usable 1Cv8.1CD in: $db_dir"

onec_bin="${ONEC_TRAINING_BIN:-$(command -v 1cv8t || true)}"
[[ -n "$onec_bin" && -x "$onec_bin" ]] || die "Educational 1cv8t is required."
[[ "$(basename -- "$onec_bin")" == "1cv8t" ]] || die "Expected educational 1cv8t."

output="$root/artifacts/warehouse.dt"
[[ ! -e "$output" ]] || die "Refusing to overwrite existing $output"
mkdir -p -- "$(dirname -- "$output")"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/onec-dump.XXXXXXXX")"
trap 'rm -rf -- "$tmp"' EXIT
runner=("$onec_bin")
if [[ -z "${DISPLAY:-}" ]]; then
  command -v xvfb-run >/dev/null 2>&1 || die "Install xvfb-run for headless export."
  runner=(xvfb-run -a "$onec_bin")
fi

if ! timeout --kill-after=10s "${ONEC_TIMEOUT_SEC:-900}" \
  "${runner[@]}" DESIGNER /F "$db_dir" /DumpIB "$output" \
  /DisableStartupDialogs /Out "$tmp/dump.log" >"$tmp/console.log" 2>&1; then
  [[ ! -f "$tmp/dump.log" ]] || cat "$tmp/dump.log" >&2
  cat "$tmp/console.log" >&2
  rm -f -- "$output"
  die "Cannot dump infobase to .dt."
fi
[[ -s "$output" ]] || die "Empty .dt after export."
printf 'PASS: saved %s (%s bytes)\n' "$output" "$(stat -c %s "$output")"
printf 'WARNING: inspect for personal information before uploading .dt.\n'
