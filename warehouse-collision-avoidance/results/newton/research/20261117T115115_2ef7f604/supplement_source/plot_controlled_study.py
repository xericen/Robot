"""Partition a controlled study before plotting to avoid confounding cohorts/maps."""
import argparse
import json
from pathlib import Path
import pandas as pd
from plot_newton_results import plot


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("folder",type=Path)
    args=parser.parse_args()
    df=pd.read_csv(args.folder/"measurements.csv")
    summaries=[]
    for keys,group in df.groupby(["map","encounter_mode","population_mode"]):
        name="_".join(keys)
        out=args.folder/"figs"/name
        out.mkdir(parents=True,exist_ok=True)
        source=out/"source.csv";group.to_csv(source,index=False)
        summaries.append({"group":name,"metrics":plot(source,out)})
    (args.folder/"figure_summary.json").write_text(json.dumps(summaries,ensure_ascii=False,indent=2))


if __name__=="__main__": main()
