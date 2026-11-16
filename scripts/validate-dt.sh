#!/usr/bin/env bash
# Validate a .dt with the official educational version of 1C:Enterprise (1cv8t).
set -euo pipefail

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s path/to/warehouse.dt\n' "$0" >&2
  exit 2
fi

[[ "${1,,}" == *.dt ]] || fail "Expected a .dt file, got: $1"
[[ -f "$1" ]] || fail "DT not found: $1"
[[ -s "$1" ]] || fail "DT file is empty: $1"

if LC_ALL=C head -c 200 "$1" | grep -aq '^version https://git-lfs.github.com/spec/v1'; then
  fail 'DT is a Git LFS pointer, not the database. Run git lfs pull.'
fi

dt_file="$(realpath -- "$1")"
onec_bin="${ONEC_TRAINING_BIN:-}"
if [[ -z "$onec_bin" ]]; then
  if command -v 1cv8t >/dev/null 2>&1; then
    onec_bin="$(command -v 1cv8t)"
  else
    shopt -s nullglob
    candidates=(/opt/1cv8t/x86_64/*/1cv8t /opt/1cv8/x86_64/*/1cv8t)
    shopt -u nullglob
    if [[ ${#candidates[@]} -eq 1 ]]; then
      onec_bin="${candidates[0]}"
    else
      fail '1cv8t not found. Set ONEC_TRAINING_BIN to the educational platform executable.'
    fi
  fi
fi
[[ "$(basename -- "$onec_bin")" == '1cv8t' ]] || fail 'Only the educational platform executable named 1cv8t is allowed.'
[[ -x "$onec_bin" ]] || fail "Not executable: $onec_bin"

workdir="$(mktemp -d "${TMPDIR:-/tmp}/onec-ci.XXXXXXXX")"
trap 'rm -rf -- "$workdir"' EXIT
mkdir -p "$workdir/ib" "$workdir/log"

runner=("$onec_bin")
if [[ -z "${DISPLAY:-}" ]]; then
  command -v xvfb-run >/dev/null 2>&1 || fail 'DISPLAY is unset and xvfb-run is missing.'
  runner=(xvfb-run -a "$onec_bin")
fi

run_stage() {
  local stage="$1"
  shift
  local output_log="$workdir/log/${stage}.log"
  local console_log="$workdir/log/${stage}.console.log"
  local code
  printf '[1C] %s\n' "$stage"
  if timeout --signal=TERM --kill-after=10s "${ONEC_TIMEOUT_SEC:-900}" \
    "${runner[@]}" DESIGNER /F "$workdir/ib" \
    "$@" /DisableStartupDialogs /Out "$output_log" >"$console_log" 2>&1; then
    :
  else
    code=$?
    printf 'Stage %s failed (exit %s).\n' "$stage" "$code" >&2
    [[ ! -f "$output_log" ]] || cat "$output_log" >&2
    cat "$console_log" >&2
    exit 1
  fi
  if [[ -s "$output_log" ]]; then
    cat "$output_log"
  fi
}

run_stage restore /RestoreIB "$dt_file"
[[ -n "$(find "$workdir/ib" -maxdepth 2 -type f -iname '1cv8.1cd' -print -quit)" ]] || \
  fail 'Restore exited successfully, but no 1Cv8.1CD file was created.'

run_stage check-config /CheckConfig \
  -ConfigLogIntegrity -IncorrectReferences -ThinClient \
  -ThickClientManagedApplication -Server -HandlersExistence -ExtendedModulesCheck

run_stage check-infobase /IBCheckAndRepair -LogAndRefsIntegrity -TestOnly
run_stage export-config /DumpCfg "$workdir/verified.cf"
[[ -s "$workdir/verified.cf" ]] || fail 'Configuration export did not produce a nonempty .cf file.'

run_stage export-db-config /DumpDBCfg "$workdir/database-config.cf"
[[ -s "$workdir/database-config.cf" ]] || fail 'Database configuration export did not produce a nonempty .cf file.'

printf 'PASS: educational 1C restored the DT, checked configuration and infobase, and exported both CF variants.\n'
printf 'NOTE: business rules and document posting still require scenario tests in 1C.\n'
