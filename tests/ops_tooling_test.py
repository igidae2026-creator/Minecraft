from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from helpers import ROOT


def test_ops_tooling_executes_cleanly(tmp_path: Path):
    subprocess.run([sys.executable, str(ROOT / "ops" / "render_network.py")], check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(ROOT / "ops" / "validate_rpg.py")], check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(ROOT / "ops" / "runtime_integrity.py")], check=True, cwd=ROOT)
    subprocess.run(["bash", str(ROOT / "ops" / "healthcheck.sh")], check=True, cwd=ROOT)

    metrics_path = tmp_path / "metrics.prom"
    subprocess.run(["bash", str(ROOT / "ops" / "metrics_exporter.sh"), str(metrics_path)], check=True, cwd=ROOT)
    assert metrics_path.is_file()
    text = metrics_path.read_text(encoding="utf-8")
    assert "rpg_network_servers_total" in text
    assert "rpg_network_plugins_per_server" in text
    assert "rpg_network_runtime_artifact_exports" in text
    assert "rpg_network_runtime_experiment_exports" in text
    assert "rpg_network_runtime_incident_exports" in text

    for script in (ROOT / "ops").glob("*.sh"):
        subprocess.run(["bash", "-n", str(script)], check=True, cwd=ROOT)
