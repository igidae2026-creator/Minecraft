from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from helpers import ROOT


def test_ops_truth_and_reconciliation_surfaces_execute_cleanly(tmp_path: Path):
    subprocess.run([sys.executable, str(ROOT / "ops" / "validate_runtime_truth.py")], check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(ROOT / "ops" / "reconcile_runtime.py")], check=True, cwd=ROOT)

    metrics_path = tmp_path / "metrics.prom"
    subprocess.run(["bash", str(ROOT / "ops" / "metrics_exporter.sh"), str(metrics_path)], check=True, cwd=ROOT)
    text = metrics_path.read_text(encoding="utf-8")
    assert "rpg_network_runtime_experiment_exports" in text
    assert "rpg_network_runtime_incident_exports" in text


def test_runbook_and_cluster_orchestration_surfaces_exist():
    assert (ROOT / "ops" / "RUNBOOK.md").is_file()
    assert (ROOT / "ops" / "orchestrate_cluster.sh").is_file()
    assert (ROOT / "ops" / "recover_runtime.sh").is_file()
