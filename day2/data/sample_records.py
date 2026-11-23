"""S1: 20 everyday shop items with GST rate changes from the 56th GST Council Meeting."""

from collections import Counter

SAMPLE_RECORDS = [
    {
        "id": 1,
        "category": "Personal Care",
        "item_or_topic": "Toilet soap bars",
        "old_rule": "18% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 2,
        "category": "Personal Care",
        "item_or_topic": "Hair oil",
        "old_rule": "18% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 3,
        "category": "Personal Care",
        "item_or_topic": "Shampoos",
        "old_rule": "18% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 4,
        "category": "Personal Care",
        "item_or_topic": "Toothpaste",
        "old_rule": "18% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 5,
        "category": "Personal Care",
        "item_or_topic": "Toothbrushes",
        "old_rule": "18% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 6,
        "category": "Dairy & Bakery",
        "item_or_topic": "Ultra-High Temperature (UHT) milk",
        "old_rule": "5% GST",
        "new_rule": "Nil (0% GST)",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 7,
        "category": "Dairy & Bakery",
        "item_or_topic": "Pre-packaged and labelled chena or paneer",
        "old_rule": "5% GST",
        "new_rule": "Nil (0% GST)",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 8,
        "category": "Dairy & Bakery",
        "item_or_topic": "Butter, ghee, and dairy spreads",
        "old_rule": "12% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 9,
        "category": "Dairy & Bakery",
        "item_or_topic": "Indian breads (chapati, roti, paratha, parotta)",
        "old_rule": "5% GST",
        "new_rule": "Nil (0% GST)",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 10,
        "category": "Packaged Food",
        "item_or_topic": "Packaged namkeens and bhujia",
        "old_rule": "12% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 11,
        "category": "Packaged Food",
        "item_or_topic": "Pasta and instant noodles",
        "old_rule": "12% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 12,
        "category": "Packaged Food",
        "item_or_topic": "Sauces and jams",
        "old_rule": "12% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 13,
        "category": "Packaged Food",
        "item_or_topic": "Chocolates and cornflakes",
        "old_rule": "18% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 14,
        "category": "Stationery",
        "item_or_topic": "Exercise books, graph books, and notebooks",
        "old_rule": "12% GST",
        "new_rule": "Nil (0% GST)",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 15,
        "category": "Stationery",
        "item_or_topic": "Pencils, crayons, and pastels",
        "old_rule": "12% GST",
        "new_rule": "Nil (0% GST)",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 16,
        "category": "Stationery",
        "item_or_topic": "Erasers",
        "old_rule": "5% GST",
        "new_rule": "Nil (0% GST)",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 17,
        "category": "Stationery",
        "item_or_topic": "Pencil sharpeners",
        "old_rule": "12% GST",
        "new_rule": "Nil (0% GST)",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 18,
        "category": "Stationery",
        "item_or_topic": "Geometry boxes and colour boxes",
        "old_rule": "12% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 19,
        "category": "Household & Mobility",
        "item_or_topic": "Bicycles and bicycle parts",
        "old_rule": "12% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    },
    {
        "id": 20,
        "category": "Household & Mobility",
        "item_or_topic": "Tableware, kitchenware, and household articles",
        "old_rule": "12% / 18% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555"
    }
]


def print_all(records):
    print(f"\n=== All GST Rate Change Records ({len(records)} items) ===")
    for r in records:
        print(
            f"[{r['id']:02d}] {r['item_or_topic']} ({r['category']}) | "
            f"{r['old_rule']} -> {r['new_rule']} | Effective: {r['effective_from']}"
        )


def search_by_keyword(records, keyword):
    kw = keyword.strip().lower()
    return [
        r for r in records
        if kw in r["item_or_topic"].lower()
        or kw in r["category"].lower()
        or kw in r["old_rule"].lower()
        or kw in r["new_rule"].lower()
    ]


def count_per_category(records):
    return dict(Counter(r["category"] for r in records))


if __name__ == "__main__":
    print_all(SAMPLE_RECORDS)

    print("\n=== Count Per Category ===")
    for cat, cnt in count_per_category(SAMPLE_RECORDS).items():
        print(f"- {cat}: {cnt}")

    query = input("\nEnter a keyword to search (e.g., milk, soap, notebook, bicycle): ").strip()
    if query:
        matches = search_by_keyword(SAMPLE_RECORDS, query)
        print(f"\nFound {len(matches)} match(es) for '{query}':")
        for m in matches:
            print(f"  - [{m['id']:02d}] {m['item_or_topic']}: {m['old_rule']} -> {m['new_rule']}")
