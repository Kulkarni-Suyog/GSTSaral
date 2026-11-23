import sys
from pathlib import Path

DAY2_ROOT = Path(__file__).resolve().parents[1]
if str(DAY2_ROOT) not in sys.path:
    sys.path.insert(0, str(DAY2_ROOT))

from app.records import get_all_records, search_records


def main() -> None:
    records = get_all_records()
    print("=== GSTSaral CLI (Day 2 - No API Key Needed) ===")
    print(f"Loaded {len(records)} GST records.\n")

    for r in records[:5]:
        print(
            f"[{r.get('id', 0):02d}] {r.get('item_or_topic', 'N/A')} ({r.get('category', 'General')}) "
            f"-> Old: {r.get('old_rule', 'N/A')} | New: {r.get('new_rule', 'N/A')}"
        )

    print("\nType a GST question below (or 'exit' to quit):")
    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting GSTSaral CLI.")
            break

        if not question:
            continue
        if question.lower() in {"exit", "quit", "q"}:
            print("Goodbye!")
            break

        matches = search_records(question)
        if not matches:
            print("\nGSTSaral: No matching GST rule found in Day 2 sample records.")
            continue

        print("\nGSTSaral:")
        for idx, r in enumerate(matches, start=1):
            year_or_date = (
                r.get("rule_year")
                or r.get("effective_date")
                or r.get("year")
                or "Latest"
            )
            source = r.get("source") or r.get("reference") or "GST Council / CBIC"
            old_rule = r.get("old_rule", "N/A")
            new_rule = r.get("new_rule", "N/A")

            print(
                f"[{idx}] {r.get('item_or_topic', 'N/A')} ({r.get('category', 'General')} | {year_or_date})\n"
                f"    Current Rule : {new_rule}\n"
                f"    Previous Rule: {old_rule}\n"
                f"    Source       : {source}"
            )
            if old_rule != new_rule and old_rule != "N/A":
                print("    [Latest Rule Wins] Newer rule overrides the previous rule.")


if __name__ == "__main__":
    main()