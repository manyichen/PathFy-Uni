"""统计招聘 Excel 中每个岗位名称的记录条数，输出 CSV。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets" / "20260226105856_457.xls"
OUTPUT_CSV = ROOT / "datasets" / "job_title_record_counts.csv"
OUTPUT_SUMMARY = ROOT / "datasets" / "job_title_record_counts_summary.txt"


def main() -> None:
    df = pd.read_excel(SOURCE, engine="xlrd")
    if df.empty:
        raise SystemExit("源文件为空")

    col_job = "岗位名称"
    col_company = "公司名称"
    col_code = "岗位编码"
    for required in (col_job, col_company, col_code):
        if required not in df.columns:
            raise SystemExit(f"缺少列: {required}，实际列: {list(df.columns)}")

    titles = df[col_job].astype(str).str.strip()
    titles = titles.replace({"nan": "", "None": "", "NaT": ""})
    empty_rows = int((titles == "").sum())

    valid = df[titles != ""].copy()
    valid["_title"] = valid[col_job].astype(str).str.strip()

    stats = (
        valid.groupby("_title", dropna=False)
        .agg(
            record_count=(col_job, "size"),
            company_count=(col_company, lambda s: s.astype(str).str.strip().nunique()),
            job_code_count=(col_code, lambda s: s.astype(str).str.strip().nunique()),
        )
        .reset_index()
        .rename(columns={"_title": "job_title"})
        .sort_values(["record_count", "job_title"], ascending=[False, True])
    )
    total = len(df)
    stats["pct_of_total"] = (stats["record_count"] / total * 100).round(4)
    stats["rank"] = range(1, len(stats) + 1)
    stats = stats[["rank", "job_title", "record_count", "pct_of_total", "company_count", "job_code_count"]]

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    stats.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    top10_sum = int(stats.head(10)["record_count"].sum())
    with OUTPUT_SUMMARY.open("w", encoding="utf-8") as f:
        f.write(f"source_file: {SOURCE.name}\n")
        f.write(f"total_rows: {total}\n")
        f.write(f"empty_job_title_rows: {empty_rows}\n")
        f.write(f"unique_job_titles: {len(stats)}\n")
        f.write(f"top10_record_sum: {top10_sum}\n")
        f.write(f"top10_pct_of_total: {round(top10_sum / total * 100, 2)}%\n")
        f.write(f"output_csv: {OUTPUT_CSV.name}\n")

    print(f"total_rows={total} unique_job_titles={len(stats)} empty_job_title_rows={empty_rows}")
    print(f"written: {OUTPUT_CSV}")
    print(f"written: {OUTPUT_SUMMARY}")
    print("\nTop 10:")
    print(stats.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
