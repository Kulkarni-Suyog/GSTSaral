"""Exploratory data analysis script printing 3 concrete facts about GSTSaral records."""

import json
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_JSON_PATH = ROOT_DIR / "data" / "records.json"


def load_dataframe() -> pd.DataFrame:
    if DATA_JSON_PATH.exists():
        with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        from app.main import FALLBACK_RECORDS
        data = FALLBACK_RECORDS
    return pd.DataFrame(data)


def main() -> None:
    df = load_dataframe()
    if df.empty:
        print("No GSTSaral records found to analyze.")
        return

    print("=" * 60)
    print("GSTSaral Dataset — 3 Data Facts (via pandas)")
    print("=" * 60)

    # Fact 1: Total records & breakdown by document / category
    total_records = len(df)
    group_col = "category" if "category" in df.columns else "document"
    top_group = df[group_col].value_counts().idxmax()
    top_group_count = int(df[group_col].value_counts().max())
    print(
        f"Fact 1 (Coverage): The dataset contains {total_records} total GST records, "
        f"with '{top_group}' having the largest share ({top_group_count} records)."
    )

    # Fact 2: Most common new GST rule / rate slab
    top_new_rule = df["new_rule"].value_counts().idxmax()
    top_new_rule_count = int(df["new_rule"].value_counts().max())
    pct_share = (top_new_rule_count / total_records) * 100
    print(
        f"Fact 2 (Dominant New Slab): '{top_new_rule}' is the most frequent updated rule, "
        f"appearing in {top_new_rule_count} of {total_records} records ({pct_share:.1f}%)."
    )

    # Fact 3: Proportion of items moved to Nil (0% GST) & distinct effective dates
    nil_count = int(df["new_rule"].astype(str).str.contains(r"\b(?:Nil|0%|exempt)\b", case=False, regex=True).sum())
    unique_dates = df["effective_from"].nunique() if "effective_from" in df.columns else 0
    print(
        f"Fact 3 (Zero-Tax Relief & Dates): {nil_count} record(s) carry a Nil/0%/Exempt rate, "
        f"spanning {unique_dates} distinct effective date(s)."
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
