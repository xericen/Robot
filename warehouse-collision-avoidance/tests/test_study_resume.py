import csv
import json
import sys
import pytest


def test_resume_keeps_completed_actual_runs(tmp_path,monkeypatch):
    import controlled_study as study
    monkeypatch.setattr(study,"ROOT",tmp_path)
    actual_execute=study.execute
    calls=[]
    def fail_after_three(**kwargs):
        if len(calls)==3:
            raise RuntimeError("test interruption")
        result=actual_execute(**kwargs)
        calls.append(result)
        return result
    monkeypatch.setattr(study,"execute",fail_after_three)
    monkeypatch.setattr(sys,"argv",["controlled_study.py","--counts","1","--populations","workers",
                                   "--repeats","2","--frames","2"])
    with pytest.raises(RuntimeError,match="test interruption"):
        study.main()
    folder=next((tmp_path/"studies").iterdir())
    first=list(csv.DictReader((folder/"measurements.csv").open()))
    assert len(first)==3
    original_ids={r["run_id"] for r in first}
    assert json.loads((folder/"progress.json").read_text())["phase"]=="error"
    monkeypatch.setattr(study,"execute",actual_execute)
    monkeypatch.setattr(sys,"argv",["controlled_study.py","--resume",str(folder)])
    study.main()
    rows=list(csv.DictReader((folder/"measurements.csv").open()))
    assert len(rows)==6 and original_ids <= {r["run_id"] for r in rows}
    assert len({r["run_id"] for r in rows})==6
    assert json.loads((folder/"progress.json").read_text())["phase"]=="complete"
