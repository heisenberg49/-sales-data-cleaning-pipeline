"""
Sales data cleaning pipeline.

Reads every CSV and Excel file in data/raw, cleans and validates them, then
writes a clean dataset to data/clean and an exceptions report to reports.

Usage:
    python src/clean_sales.py
"""

import logging
import sys
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")
CLEAN_DIR = Path("data/clean")
REPORTS_DIR = Path("reports")
LOG_DIR = Path("logs")

# rename map for the different names the same field arrives under
COLUMN_MAP = {
    "customername": "customer_name",
    "cust_name": "customer_name",
    "client_name": "customer_name",
    "invoice_no": "order_id",
    "order_no": "order_id",
    "qty": "quantity",
    "rate": "unit_price",
}

REGION_MAP = {"N": "North", "S": "South", "E": "East", "W": "West", "": "Unknown"}

PRODUCT_MAP = {
    "steel pipe 2in": "Steel Pipe 2in",
    "copper wire 5m": "Copper Wire 5m",
    "valve assembly": "Valve Assembly",
    "gasket set": "Gasket Set",
}

TOTAL_ROW_LABELS = {"total", "grand total", "subtotal"}


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "cleaning.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_file(path: Path) -> pd.DataFrame:
    """Load one file with every column as text so nothing is auto-converted."""
    if path.suffix.lower() == ".csv":
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
        except UnicodeDecodeError:
            logging.warning("%s is not utf-8, falling back to cp1252", path.name)
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="cp1252")
    else:
        df = pd.read_excel(path, dtype=str, keep_default_na=False)

    df["source_file"] = path.name
    return df


def load_all(raw_dir: Path) -> pd.DataFrame:
    """Combine every raw file into one dataframe."""
    paths = [p for p in sorted(raw_dir.rglob("*"))
             if p.suffix.lower() in {".csv", ".xlsx", ".xls"}]

    if not paths:
        raise FileNotFoundError(
            f"no data files found in {raw_dir}. "
            "Run python src/generate_sample_data.py first."
        )

    frames = [load_file(p) for p in paths]
    df = pd.concat(frames, ignore_index=True, sort=False)
    logging.info("loaded %d rows from %d files", len(df), len(paths))
    return df


def standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns.str.strip().str.lower()
        .str.replace(r"[^\w\s]", "", regex=True)
        .str.replace(r"\s+", "_", regex=True)
    )
    return df.rename(columns=COLUMN_MAP)


def remove_structural_junk(df: pd.DataFrame) -> pd.DataFrame:
    """Drop total rows, empty rows and rows with no order id."""
    before = len(df)
    df = df[~df["customer_name"].str.strip().str.lower().isin(TOTAL_ROW_LABELS)]
    df = df[df["order_id"].str.strip() != ""]
    logging.info("removed %d structural junk rows", before - len(df))
    return df


def clean_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Parse dates with explicit formats in passes, never by inference."""
    df = df.copy()

    day_first = pd.to_datetime(df["order_date"], format="%d/%m/%Y", errors="coerce")
    iso = pd.to_datetime(df["order_date"], format="%Y-%m-%d", errors="coerce")
    short = pd.to_datetime(df["order_date"], format="%d-%b-%y", errors="coerce")
    df["order_date_clean"] = day_first.fillna(iso).fillna(short)

    # excel serial numbers that lost their date formatting
    serial = df["order_date"].str.match(r"^\d{5}$") & df["order_date_clean"].isna()
    if serial.any():
        df.loc[serial, "order_date_clean"] = pd.to_datetime(
            df.loc[serial, "order_date"].astype(int), unit="D", origin="1899-12-30"
        )
        logging.info("converted %d excel serial dates", int(serial.sum()))

    unparsed = df["order_date_clean"].isna().sum()
    if unparsed:
        logging.warning("%d dates could not be parsed", unparsed)

    return df


def clean_numeric(series: pd.Series) -> pd.Series:
    """Strip currency symbols and separators, then coerce to a number."""
    return pd.to_numeric(
        series.str.replace(r"[^\d.\-]", "", regex=True).replace("", None),
        errors="coerce",
    )


def clean_values(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["quantity"] = clean_numeric(df["quantity"])
    df["unit_price"] = clean_numeric(df["unit_price"])
    df["region"] = df["region"].str.strip().str.title().replace(REGION_MAP)
    df["status"] = df["status"].str.strip().str.title()
    df["product"] = df["product"].str.strip().str.lower().map(PRODUCT_MAP)

    df["customer_key"] = (
        df["customer_name"].str.strip().str.lower()
        .str.replace(r"[^\w\s]", "", regex=True)
        .str.replace(r"\b(pvt|ltd|limited|co|and)\b", "", regex=True)
        .str.replace(r"\s+", " ", regex=True).str.strip()
    )
    return df


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """The real key is order plus product, not order alone."""
    before = len(df)
    df = df.drop_duplicates()
    df = df.drop_duplicates(subset=["order_id", "product"], keep="last")
    logging.info("removed %d duplicate rows", before - len(df))
    return df


def build_exceptions(df: pd.DataFrame) -> pd.DataFrame:
    """Collect every row that fails a rule, with the reason attached."""
    collected = []

    def flag(mask: pd.Series, reason: str) -> None:
        if mask.any():
            subset = df.loc[mask].copy()
            subset["exception_reason"] = reason
            collected.append(subset)

    flag(df["order_date_clean"].isna(), "date could not be parsed")
    flag(df["quantity"].isna(), "quantity missing or not numeric")
    flag(df["quantity"] < 0, "negative quantity")
    flag(df["unit_price"].isna(), "unit price could not be parsed")
    flag(df["product"].isna(), "product not in known list")
    flag(df["order_date_clean"] > pd.Timestamp.today(), "order date in the future")

    if not collected:
        return pd.DataFrame()

    return pd.concat(collected, ignore_index=True)


def validate(df: pd.DataFrame) -> None:
    """Fail loudly rather than shipping a quietly wrong file."""
    assert len(df) > 0, "no rows survived cleaning"
    assert df["order_date"].notna().all(), "unparsed dates in output"
    assert df["quantity"].notna().all(), "missing quantities in output"
    assert not df.duplicated(subset=["order_id", "product"]).any(), "duplicate line items"
    logging.info("validation passed")


def export(clean: pd.DataFrame, exceptions: pd.DataFrame) -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    clean.to_csv(CLEAN_DIR / "sales_clean.csv", index=False)

    with pd.ExcelWriter(CLEAN_DIR / "sales_clean.xlsx", engine="openpyxl") as writer:
        clean.to_excel(writer, sheet_name="Clean Data", index=False)
        if not exceptions.empty:
            exceptions.to_excel(writer, sheet_name="Exceptions", index=False)

    if not exceptions.empty:
        exceptions.to_csv(REPORTS_DIR / "exceptions.csv", index=False)

    logging.info("wrote %d clean rows and %d exception rows", len(clean), len(exceptions))


def main() -> None:
    setup_logging()
    logging.info("run started")

    df = load_all(RAW_DIR)
    df = standardise_columns(df)
    df = remove_structural_junk(df)
    df = clean_dates(df)
    df = clean_values(df)
    df = deduplicate(df)

    exceptions = build_exceptions(df)

    keep = (
        df["order_date_clean"].notna()
        & df["quantity"].notna()
        & df["unit_price"].notna()
        & df["product"].notna()
    )
    clean = df.loc[keep, [
        "order_id", "order_date_clean", "customer_key", "region",
        "product", "quantity", "unit_price", "status", "source_file",
    ]].rename(columns={"order_date_clean": "order_date", "customer_key": "customer_name"})

    clean["customer_name"] = clean["customer_name"].str.title()
    clean["line_total"] = clean["quantity"] * clean["unit_price"]

    validate(clean)
    export(clean, exceptions)
    logging.info("run finished")


if __name__ == "__main__":
    main()
