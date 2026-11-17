"""Exercise WIZ's endpoint with an isolated real CSV and no Newton process."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
from newton_results import FIELDS, write_rows


class ResponseExit(Exception):
    def __init__(self, code, data=None, **kwargs):
        self.code, self.data = code, data


def test_saved_endpoint_reads_csv_without_simulation(tmp_path):
    project = Path(__file__).resolve().parents[2]
    root = tmp_path / "warehouse-collision-avoidance"
    (root / ".venv/bin").mkdir(parents=True)
    (root / ".venv/bin/python").symlink_to(sys.executable)
    (root / "newton_results.py").write_text((project / "warehouse-collision-avoidance/newton_results.py").read_text())
    row = dict.fromkeys(FIELDS, None)
    row.update(map="map1", algorithm="VO", success=0, timeout=1, algo_time_avg_ms=.1)
    write_rows(root / "results/newton/map1_vo_medium_42.csv", [row])
    spec = importlib.util.spec_from_file_location("newton_csv_api", project / "src/app/page.algorithm.run/api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.wiz = SimpleNamespace(
        project=SimpleNamespace(path=lambda: str(tmp_path)),
        request=SimpleNamespace(query=lambda key, default=None: "saved" if key == "mode" else default),
        response=SimpleNamespace(status=lambda code, data=None, **kw: (_ for _ in ()).throw(ResponseExit(code, data, **kw))),
    )
    try:
        module.run_newton()
    except ResponseExit as response:
        assert response.code == 200
        assert len(response.data) == 1
        saved = response.data[0]
        assert saved["map"] == "map1" and saved["algorithm"] == "VO"
        assert saved["arrival_time_s"] is None
        assert saved["success"] + saved["timeout"] == 1
    else:
        raise AssertionError("WIZ response was not returned")
