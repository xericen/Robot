"""Read-only source analysis; all derived results live in a new immutable run folder."""
from __future__ import annotations
import argparse,json,subprocess,sys,uuid
from datetime import datetime,timezone
from pathlib import Path
import research_data as data

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--primary",type=Path,default=data.MAIN)
    p.add_argument("--pilot",type=Path,default=data.PILOT)
    p.add_argument("--output",type=Path)
    p.add_argument("--resume-analysis",action="store_true")
    p.add_argument("--supplement",action="store_true")
    args=p.parse_args()
    data.MAIN=args.primary;data.PILOT=args.pilot
    out=args.output or data.ROOT/"results/newton/research"/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"_"+uuid.uuid4().hex[:8])
    if out.exists() and not args.resume_analysis:p.error("Output exists; use --resume-analysis for derived files only.")
    out.mkdir(parents=True,exist_ok=True)
    if not all((x/"measurements.csv").is_file() for x in (data.MAIN,data.PILOT)):
        (out/"missing.json").write_text(json.dumps({"status":"missing","primary":str(data.MAIN),"pilot":str(data.PILOT),
            "action":"Specify existing study directories with --primary/--pilot; use controlled_study.py --help for new experiments."},indent=2))
        raise SystemExit("Missing originals: no research values generated.")
    audit_path=out/"audit.json"
    if not audit_path.exists():audit_path.write_text(json.dumps(data.audit(),ensure_ascii=False,indent=2))
    audited=data.read_json(audit_path);data.assert_originals(audited)
    if audited["issues"] or audited["mismatches"]:raise ValueError(audited["issues"]+audited["mismatches"])
    from research_statistics import write_tables
    from research_orca import analyze_failures
    from research_layouts import analyze_layouts
    from research_figures import generate,supplement_figures
    from research_telemetry import enrich
    from research_report import build
    original,pilot=data.inputs()
    write_tables(original,pilot,out)
    if not (out/"orca_summary.json").exists():analyze_failures(original,out)
    if not (out/"warehouse_layout_analysis.csv").exists():analyze_layouts(out)
    generate(out)
    if args.supplement and not (out/"supplement_complete.json").exists():
        subprocess.run([sys.executable,str(data.ROOT/"research_supplement.py"),str(out)],check=True,cwd=data.ROOT)
    if (out/"supplement_complete.json").exists():enrich(out);supplement_figures(out)
    bundle=build(out);data.assert_originals(audited)
    manifest={"status":"complete","primary_runs":len(original),"pilot_runs":len(pilot),
              "new_runs":bundle["supplement_runs"],"originals_unchanged":True,
              "files":[str(f.relative_to(out)) for f in sorted(out.rglob("*")) if f.is_file()]}
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(out)
if __name__=="__main__":main()
