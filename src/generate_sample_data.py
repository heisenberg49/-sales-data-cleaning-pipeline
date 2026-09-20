"""
Generate a messy sample sales export.

This stands in for the client's real files, which are not in this repository.
It reproduces the same problems found in the original data: inconsistent
customer names, mixed date formats, prices stored as text, duplicate line
items, blank regions and out-of-range quantities.

Usage:
    python src/generate_sample_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUTPUT_PATH = Path("data/raw/sales_raw_sample.csv")
N_ROWS = 420
SEED = 7

CUSTOMERS = [
    "Sharma Traders", "sharma traders", "SHARMA TRADERS PVT LTD", "Sharma Tradrs",
    "Verma & Sons", "verma and sons", "Verma Sons Ltd", "Nova Supplies",
    "NOVA SUPPLIES", "Nova Suplies Co", "Kiran Enterprises", "kiran enterprise",
    "Deep Metals", "Deep Metal Works",
]
REGIONS = ["North", "north", "N", " South", "South", "S", "East", "West", "west", ""]
PRODUCTS = [
    "Steel Pipe 2in", "steel pipe 2in ", "Copper Wire 5m", "Copper Wire 5m",
    "Valve Assembly", "valve assembly", "Gasket Set", "Gasket Set ",
]
STATUSES = ["Completed", "completed", "COMPLETED", "Cancelled", "cancelled", "Pending", "Returned"]
DATES = ["14/03/2026", "2026-03-14", "05/04/2026", "2026-04-05", "18-Mar-26", "45001", ""]
DATE_WEIGHTS = [0.34, 0.22, 0.16, 0.12, 0.09, 0.04, 0.03]
QTY = ["1", "2", "3", "5", "10", "-2", ""]
QTY_WEIGHTS = [0.28, 0.24, 0.18, 0.14, 0.10, 0.03, 0.03]


def build_messy_frame(n_rows: int = N_ROWS, seed: int = SEED) -> pd.DataFrame:
    """Return a dataframe with the same defects as the original client export."""
    rng = np.random.default_rng(seed)

    df = pd.DataFrame({
        "Order ID": [f"{100000 + int(rng.integers(0, 260)):06d}" for _ in range(n_rows)],
        " Customer Name": rng.choice(CUSTOMERS, n_rows),
        "Region": rng.choice(REGIONS, n_rows),
        "Product": rng.choice(PRODUCTS, n_rows),
        "Order Date": rng.choice(DATES, n_rows, p=DATE_WEIGHTS),
        "Qty": rng.choice(QTY, n_rows, p=QTY_WEIGHTS),
        "Unit Price": [f"Rs {rng.integers(50, 4000):,}" for _ in range(n_rows)],
        "Status": rng.choice(STATUSES, n_rows),
    })

    # a few prices typed as free text
    df.loc[df.sample(6, random_state=1).index, "Unit Price"] = "approx 1200"

    # the totals row every Excel export seems to carry
    df.loc[len(df)] = ["", "Grand Total", "", "", "", "", "", ""]

    return df


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = build_messy_frame()
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"wrote {len(df):,} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
