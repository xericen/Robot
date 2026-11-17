"""Keep test simulations from replacing measured experiment CSVs."""
import pytest


@pytest.fixture(autouse=True)
def isolate_newton_results(tmp_path, monkeypatch):
    import newton_results
    monkeypatch.setattr(newton_results, "ROOT", tmp_path / "newton")
