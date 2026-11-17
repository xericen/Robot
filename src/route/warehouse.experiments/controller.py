"""Serve only completed controlled-study PNGs; arbitrary project files are never served."""
import json
from pathlib import Path
import re
import flask

parts=flask.request.path.split("/warehouse-experiments/",1)[-1].split("/")
if len(parts)==3 and parts[0]=="research":
    research_root=(Path(wiz.project.path())/"warehouse-collision-avoidance/results/newton/research").resolve()
    if not re.fullmatch(r"[0-9]{8}T[0-9]{6}_[a-f0-9]{8}",parts[1]):
        wiz.response.abort(404)
    folder=research_root/parts[1]
    try:
        bundle=json.loads((folder/"dashboard.json").read_text())
        allowed={"algorithm_comparison.csv","scenario_comparison.csv","scalability_analysis.csv",
                 "warehouse_layout_analysis.csv","orca_failure_analysis.csv","research_report.md",
                 "presentation_summary.md","paired_comparisons.csv","supplemental_analysis.csv",
                 "measurements.csv","map_comparison.csv","statistical_method.json"}
        image=parts[2] in bundle.get("figures",[])
        target=(folder/("figs" if image else "")/parts[2]).resolve()
        valid=(image or parts[2] in allowed) and target.is_relative_to(folder.resolve()) and target.is_file()
    except (OSError,ValueError):
        valid=False
    if not valid:
        wiz.response.abort(404)
    response=flask.send_file(str(target),conditional=True,as_attachment=not image)
    response.headers["Cache-Control"]="private, max-age=300"
    wiz.response.response(response)
if (len(parts)!=3 or not re.fullmatch(r"[0-9]{8}T[0-9]{12}Z_[a-f0-9]{8}",parts[0])
        or not re.fullmatch(r"map[1-6]_(head_on|crossing|narrow_passing)_(workers|mixed)",parts[1])
        or not re.fullmatch(r"0[1-9]_[a-z_]+\.png",parts[2])):
    wiz.response.abort(404)
root=(Path(wiz.project.path())/"warehouse-collision-avoidance/results/newton/studies").resolve()
folder=root/parts[0]
try:
    state=json.loads((folder/"progress.json").read_text())
    target=(folder/"figs"/parts[1]/parts[2]).resolve()
    valid=state.get("phase")=="complete" and target.is_relative_to(root) and target.is_file()
except (OSError,ValueError):
    valid=False
if not valid:
    wiz.response.abort(404)
response=flask.send_file(str(target),mimetype="image/png",conditional=True)
response.headers["Cache-Control"]="private, max-age=300"
wiz.response.response(response)
