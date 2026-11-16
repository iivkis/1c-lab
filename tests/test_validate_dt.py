"""Tests of the wrapper only; these do NOT replace real 1C platform execution."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate-dt.sh"

MOCK_1CV8T = """#!/usr/bin/env bash
set -euo pipefail
stage=''
ib=''
config=''
log=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    /F) ib="$2"; shift 2 ;;
    /RestoreIB) stage=restore; shift 2 ;;
    /CheckConfig) stage=check-config; shift ;;
    /IBCheckAndRepair) stage=check-infobase; shift ;;
    /DumpCfg) stage=export-config; config="$2"; shift 2 ;;
    /Out) log="$2"; shift 2 ;;
    *) shift ;;
  esac
done
if [[ "${MOCK_FAIL_STAGE:-}" == "$stage" ]]; then
  printf 'Simulated platform failure\n' > "$log"
  exit 101
fi
if [[ "$stage" == restore ]]; then
  mkdir -p "$ib"
  printf 'mock database\n' > "$ib/1Cv8.1CD"
fi
if [[ "$stage" == export-config ]]; then
  printf 'mock cfg\n' > "$config"
fi
printf 'ok %s\n' "$stage" > "$log"
"""


class ValidationScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dt = self.root / "warehouse.dt"
        self.dt.write_bytes(b"mock binary DT, not a real 1C archive")
        self.bin = self.root / "1cv8t"
        self.bin.write_text(MOCK_1CV8T, encoding="utf-8")
        self.bin.chmod(0o755)

    def run_check(self, path=None, **extra):
        env = os.environ.copy()
        env.update({"ONEC_TRAINING_BIN": str(self.bin), "DISPLAY": ":99"})
        env.update(extra)
        return subprocess.run(
            ["bash", str(SCRIPT), str(path or self.dt)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def test_success_with_mock(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS: educational 1C", result.stdout)

    def test_missing_dt_fails(self):
        result = self.run_check(self.root / "missing.dt")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DT not found", result.stderr)

    def test_lfs_pointer_fails(self):
        self.dt.write_text("version https://git-lfs.github.com/spec/v1\n", encoding="utf-8")
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Git LFS pointer", result.stderr)

    def test_commercial_binary_is_rejected(self):
        commercial = self.root / "1cv8"
        commercial.write_text(MOCK_1CV8T, encoding="utf-8")
        commercial.chmod(0o755)
        result = self.run_check(ONEC_TRAINING_BIN=str(commercial))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Only the educational", result.stderr)

    def test_each_platform_stage_failure_is_detected(self):
        for stage in ("restore", "check-config", "check-infobase", "export-config"):
            with self.subTest(stage=stage):
                result = self.run_check(MOCK_FAIL_STAGE=stage)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Stage " + stage + " failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
