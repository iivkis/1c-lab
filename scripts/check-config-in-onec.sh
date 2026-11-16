#!/usr/bin/env bash
# Real integration check using the official educational 1C:Enterprise executable.
set -euo pipefail

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -s "$root/src/Configuration.xml" ]] || die "src/Configuration.xml is missing."
onec_bin="${ONEC_TRAINING_BIN:-}"
if [[ -z "$onec_bin" ]]; then onec_bin="$(command -v 1cv8t || true)"; fi
[[ -n "$onec_bin" ]] || die "Educational 1cv8t is missing. Set ONEC_TRAINING_BIN."
[[ "$(basename -- "$onec_bin")" == "1cv8t" ]] || die "Expected the educational executable 1cv8t."
[[ -x "$onec_bin" ]] || die "Not executable: $onec_bin"

workdir="$(mktemp -d "${TMPDIR:-/tmp}/onec-config.XXXXXXXX")"
keep_db=false
if [[ $# -eq 0 ]]; then
  db_dir="$workdir/ib"
elif [[ $# -eq 2 && "$1" == "--keep-db" ]]; then
  keep_db=true
  db_dir="$(realpath -m -- "$2")"
  [[ ! -e "$db_dir" ]] || die "Target already exists: $db_dir. Existing bases are never overwritten."
else
  die "Usage: $0 [--keep-db PATH_TO_NEW_INFOBASE]"
fi
mkdir -p "$db_dir" "$workdir/logs"
trap 'rm -rf -- "$workdir"' EXIT

runner=("$onec_bin")
if [[ -z "${DISPLAY:-}" ]]; then
  command -v xvfb-run >/dev/null 2>&1 || die "Install xvfb-run for headless work."
  runner=(xvfb-run -a "$onec_bin")
fi

stage() {
  local name="$1"; shift
  local status=0
  local log="$workdir/logs/${name}.log"
  local console="$workdir/logs/${name}.console.log"
  printf '\n[1C] %s\n' "$name"
  timeout --kill-after=10s "${ONEC_TIMEOUT_SEC:-900}" \
    "${runner[@]}" "$@" /Out "$log" >"$console" 2>&1 || status=$?
  [[ ! -s "$log" ]] || cat "$log"
  [[ ! -s "$console" ]] || cat "$console"
  (( status == 0 )) || die "1C stage '$name' failed (exit $status)."
}

stage create CREATEINFOBASE "File=$db_dir"
stage load DESIGNER /F "$db_dir" /LoadConfigFromFiles "$root/src" \
  -Format Hierarchical /DisableStartupDialogs
stage update DESIGNER /F "$db_dir" /UpdateDBCfg /DisableStartupDialogs
stage check DESIGNER /F "$db_dir" /CheckConfig \
  -ConfigLogIntegrity -IncorrectReferences -ThinClient \
  -ThickClientManagedApplication -Server -HandlersExistence -ExtendedModulesCheck \
  /DisableStartupDialogs
stage export DESIGNER /F "$db_dir" /DumpCfg "$workdir/verified.cf" /DisableStartupDialogs
[[ -s "$workdir/verified.cf" ]] || die "Configuration export did not produce a .cf."
[[ -s "$db_dir/1Cv8.1CD" ]] || die "No 1Cv8.1CD infobase was created."

printf '\nPASS: educational 1C imported the XML and checked the configuration.\n'
if [[ "$keep_db" == true ]]; then
  printf 'Infobase saved at: %s\n' "$db_dir"
  printf 'Open it in 1C to run acceptance tests and create sample data.\n'
else
  printf 'Temporary infobase removed on exit.\n'
fi
