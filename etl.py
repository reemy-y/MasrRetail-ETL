"""
MasrRetail ETL Pipeline
=======================
Extracts CSV source files → Cleans & validates → Loads into SQLite database.

Usage:
    python etl.py                     # runs full pipeline with default paths
    python etl.py --db my.db          # custom database path
    python etl.py --data-dir ./data   # custom data folder

Output:
    - masrretail.db          : SQLite database with 4 tables
    - rejected_rows.csv      : All rows that failed validation (with reason)
    - etl_run_log.csv        : One row per pipeline run (for dashboard log view)
"""

import os
import sys
import argparse
import sqlite3
import logging
from datetime import datetime

import pandas as pd

# CONFIG


DEFAULT_DB_PATH   = "masrretail.db"
DEFAULT_DATA_DIR  = "masrretail_data"
REJECTED_PATH     = "rejected_rows.csv"
RUN_LOG_PATH      = "etl_run_log.csv"

# Maps raw category names (dirty) → standard 5 categories
CATEGORY_MAP = {
    "dairy":          "Dairy",
    "milk":           "Dairy",
    "cheese":         "Dairy",
    "yoghurt":        "Dairy",
    "butter":         "Dairy",
    "cream":          "Dairy",
    "bread":          "Bread & Bakery",
    "bread & bakery": "Bread & Bakery",
    "bakery":         "Bread & Bakery",
    "pastry":         "Bread & Bakery",
    "meat":           "Meat & Poultry",
    "meat & poultry": "Meat & Poultry",
    "poultry":        "Meat & Poultry",
    "chicken":        "Meat & Poultry",
    "beef":           "Meat & Poultry",
    "lamb":           "Meat & Poultry",
    "seafood":        "Meat & Poultry",
    "vegetables":     "Vegetables",
    "vegetable":      "Vegetables",
    "packaged goods": "Packaged Goods",
    "packaged":       "Packaged Goods",
    "oil":            "Packaged Goods",
    "sugar":          "Packaged Goods",
    "rice":           "Packaged Goods",
    "pasta":          "Packaged Goods",
    "beverages":      "Packaged Goods",
    "snacks":         "Packaged Goods",
    "spices":         "Packaged Goods",
    "sauces":         "Packaged Goods",
}

VALID_UNITS       = {"kg", "litre", "piece", "g", "ml", "l"}
VALID_STORE_TYPES = {"Hypermarket", "Supermarket", "Minimarket"}
MAX_PRICE_EGP     = 10_000   # anything above this is flagged as corrupt

# LOGGING

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("masrretail_etl")


# STEP 1 — EXTRACT

def load_csv(filepath: str) -> pd.DataFrame:
    """
    Read a CSV file into a DataFrame.
    Returns an empty DataFrame (with a warning) if the file is missing or unreadable.
    """
    if not os.path.exists(filepath):
        log.warning(f"File not found, skipping: {filepath}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(filepath, low_memory=False)
        log.info(f"Loaded {len(df):>6,} rows from {os.path.basename(filepath)}")
        return df
    except Exception as e:
        log.error(f"Failed to read {filepath}: {e}")
        return pd.DataFrame()


# STEP 2 — CLEAN

def clean_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the price_records DataFrame:
    - Strip whitespace from string columns
    - Cast price columns to float
    - Parse recorded_date to datetime
    - Fill missing is_on_sale with False
    - Set discount_price to None where is_on_sale is False
    """
    if df.empty:
        return df

    df = df.copy()

    # Strip whitespace from all string columns
    str_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace("nan", pd.NA)

    # Numeric coercion — errors become NaN so validation catches them
    for col in ["price_egp", "discount_price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Date parsing
    if "recorded_date" in df.columns:
        df["recorded_date"] = pd.to_datetime(df["recorded_date"], errors="coerce")

    # Boolean flag
    if "is_on_sale" in df.columns:
        df["is_on_sale"] = df["is_on_sale"].fillna(False).astype(bool)

    # If not on sale, discount_price should be null
    if "discount_price" in df.columns and "is_on_sale" in df.columns:
        df.loc[~df["is_on_sale"], "discount_price"] = pd.NA

    log.info(f"clean_prices: {len(df):,} rows after cleaning")
    return df


def clean_products(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the products DataFrame:
    - Strip whitespace
    - Standardize category names via CATEGORY_MAP
    - Standardize unit to lowercase
    """
    if df.empty:
        return df

    df = df.copy()

    str_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace("nan", pd.NA)

    if "unit" in df.columns:
        df["unit"] = df["unit"].str.lower()

    log.info(f"clean_products: {len(df):,} rows after cleaning")
    return df


def clean_supermarkets(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the supermarkets DataFrame:
    - Strip whitespace
    - Standardize store_type capitalisation
    - Fill is_active with True
    """
    if df.empty:
        return df

    df = df.copy()

    str_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace("nan", pd.NA)

    if "store_type" in df.columns:
        df["store_type"] = df["store_type"].str.title()

    if "is_active" in df.columns:
        df["is_active"] = df["is_active"].fillna(True).astype(bool)

    log.info(f"clean_supermarkets: {len(df):,} rows after cleaning")
    return df


def clean_cpi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the CPI DataFrame:
    - Strip whitespace
    - Cast numeric columns
    - Validate period_month is 1-12
    """
    if df.empty:
        return df

    df = df.copy()

    str_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace("nan", pd.NA)

    for col in ["cpi_value", "base_year", "period_year", "period_month"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    log.info(f"clean_cpi: {len(df):,} rows after cleaning")
    return df


# STEP 3 — STANDARDIZE

def standardize_categories(df: pd.DataFrame, col: str = "category") -> pd.DataFrame:
    """
    Map raw category values to the 5 standard categories using CATEGORY_MAP.
    Unrecognised values are left unchanged (validation will flag them if needed).
    """
    if df.empty or col not in df.columns:
        return df

    df = df.copy()
    df[col] = df[col].map(
        lambda x: CATEGORY_MAP.get(str(x).lower(), x) if pd.notna(x) else x
    )
    return df


# STEP 4 — VALIDATE

def validate_records(df: pd.DataFrame, table: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Validate rows according to table-specific rules.
    Returns (valid_df, rejected_df).
    Rejected rows gain a 'rejection_reason' column.
    """
    if df.empty:
        return df, pd.DataFrame()

    df = df.copy()
    rejected_parts = []

    def reject(mask: pd.Series, reason: str):
        """Mark matching rows as rejected and remove from df."""
        nonlocal df
        bad = df[mask].copy()
        if bad.empty:
            return
        bad["rejection_reason"] = reason
        bad["source_table"]     = table
        bad["rejected_at"]      = datetime.now().isoformat()
        rejected_parts.append(bad)
        df = df[~mask]
        log.warning(f"  Rejected {len(bad):>4} rows [{table}] — {reason}")

    # ── PRICE_RECORDS rules 
    if table == "price_records":
        reject(df["price_egp"].isna(),                       "price_egp is null")
        reject(df["price_egp"] <= 0,                         "price_egp is zero or negative")
        reject(df["price_egp"] > MAX_PRICE_EGP,              f"price_egp exceeds {MAX_PRICE_EGP} EGP (likely corrupt)")
        reject(df["product_id"].isna(),                      "product_id is null")
        reject(df["supermarket_id"].isna(),                  "supermarket_id is null")
        reject(df["recorded_date"].isna(),                   "recorded_date is null or unparseable")
        reject(
            df.duplicated(subset=["product_id", "supermarket_id", "recorded_date"], keep="first"),
            "duplicate (product_id + supermarket_id + recorded_date)"
        )

    # PRODUCTS rules 
    elif table == "products":
        reject(df["product_name"].isna() | (df["product_name"] == ""),  "product_name is null or empty")
        reject(df["category"].isna(),                                    "category is null")

    # SUPERMARKETS rules 
    elif table == "supermarkets":
        reject(df["chain_name"].isna() | (df["chain_name"] == ""),  "chain_name is null or empty")
        reject(df["governorate"].isna(),                             "governorate is null")

    # CPI_DATA rules
    elif table == "cpi_data":
        reject(df["cpi_value"].isna(),                               "cpi_value is null")
        reject(df["cpi_value"] <= 0,                                 "cpi_value is zero or negative")
        reject(df["period_month"].isna() | ~df["period_month"].between(1, 12), "period_month outside 1-12")
        reject(df["category"].isna(),                                "category is null")

    rejected_df = pd.concat(rejected_parts, ignore_index=True) if rejected_parts else pd.DataFrame()
    log.info(f"validate_records [{table}]: {len(df):,} valid | {len(rejected_df):,} rejected")
    return df, rejected_df


# STEP 5 — LOAD

def create_schema(conn: sqlite3.Connection):
    """
    Create all 4 tables if they don't already exist.
    Matches the logical/physical schema defined in the project document.
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            product_id   INTEGER PRIMARY KEY,
            product_name TEXT    NOT NULL,
            brand        TEXT,
            category     TEXT    NOT NULL,
            sub_category TEXT,
            unit         TEXT    NOT NULL,
            barcode      TEXT    UNIQUE,
            created_at   TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS supermarkets (
            supermarket_id INTEGER PRIMARY KEY,
            chain_name     TEXT    NOT NULL,
            branch_name    TEXT,
            governorate    TEXT    NOT NULL,
            district       TEXT,
            store_type     TEXT    NOT NULL,
            is_active      INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS price_records (
            price_id       INTEGER PRIMARY KEY,
            product_id     INTEGER NOT NULL REFERENCES products(product_id),
            supermarket_id INTEGER NOT NULL REFERENCES supermarkets(supermarket_id),
            price_egp      REAL    NOT NULL CHECK (price_egp > 0),
            discount_price REAL,
            is_on_sale     INTEGER DEFAULT 0,
            recorded_date  TEXT    NOT NULL,
            source         TEXT    NOT NULL,
            load_timestamp TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cpi_data (
            cpi_id        INTEGER PRIMARY KEY,
            category      TEXT    NOT NULL,
            governorate   TEXT,
            cpi_value     REAL    NOT NULL CHECK (cpi_value > 0),
            base_year     INTEGER NOT NULL,
            period_year   INTEGER NOT NULL,
            period_month  INTEGER NOT NULL CHECK (period_month BETWEEN 1 AND 12),
            source_agency TEXT    DEFAULT 'CAPMAS'
        );

        -- Indexes for common dashboard queries
        CREATE INDEX IF NOT EXISTS idx_price_product    ON price_records(product_id);
        CREATE INDEX IF NOT EXISTS idx_price_supermarket ON price_records(supermarket_id);
        CREATE INDEX IF NOT EXISTS idx_price_date       ON price_records(recorded_date);
        CREATE INDEX IF NOT EXISTS idx_cpi_category     ON cpi_data(category, period_year, period_month);
    """)
    conn.commit()
    log.info("Schema created / verified ✓")


def load_to_sqlite(df: pd.DataFrame, table: str, db_path: str):
    """
    Upsert-safe load: insert rows, replace on primary key conflict.
    Uses INSERT OR REPLACE so re-running the pipeline on an existing
    database updates matching rows instead of crashing on duplicate keys.
    """
    if df.empty:
        log.info(f"load_to_sqlite [{table}]: nothing to load")
        return 0

    # Convert dates and booleans to SQLite
    df = df.copy()
    for col in df.select_dtypes(include="datetime64[ns]").columns:
        df[col] = df[col].dt.strftime("%Y-%m-%d")
    for col in df.select_dtypes(include="bool").columns:
        df[col] = df[col].astype(int)

    # Replace NaN/NaT with None so SQLite stores proper NULLs
    df = df.where(pd.notnull(df), None)

    cols = list(df.columns)
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join(cols)
    sql = f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"

    with sqlite3.connect(db_path) as conn:
        create_schema(conn)
        conn.executemany(sql, df.itertuples(index=False, name=None))
        conn.commit()

    log.info(f"load_to_sqlite [{table}]: {len(df):,} rows written to {db_path} (upsert)")
    return len(df)


def save_rejected(rejected_df: pd.DataFrame):
    """
    Append rejected rows to rejected_rows.csv.
    Creates the file with headers on first run, appends on subsequent runs.
    """
    if rejected_df.empty:
        return

    write_header = not os.path.exists(REJECTED_PATH)
    rejected_df.to_csv(REJECTED_PATH, mode="a", index=False, header=write_header)
    log.info(f"Rejected rows written to {REJECTED_PATH} ({len(rejected_df):,} rows)")


def log_run(run_stats: dict):
    """
    Append one row to etl_run_log.csv for the dashboard pipeline log view.
    """
    row = pd.DataFrame([run_stats])
    write_header = not os.path.exists(RUN_LOG_PATH)
    row.to_csv(RUN_LOG_PATH, mode="a", index=False, header=write_header)
    log.info(f"Run log updated → {RUN_LOG_PATH}")


# MAIN PIPELINE

def run_pipeline(data_dir: str, db_path: str):
    """
    Full ETL run:
      1. Load all 5 CSVs
      2. Clean each DataFrame
      3. Standardize categories
      4. Validate and split into valid / rejected
      5. Load valid rows into SQLite
      6. Save rejected rows and run log
    """
    start_time = datetime.now()
    log.info("=" * 60)
    log.info("MasrRetail ETL pipeline starting")
    log.info(f"  data_dir : {data_dir}")
    log.info(f"  database : {db_path}")
    log.info("=" * 60)

    total_loaded   = 0
    total_rejected = 0
    all_rejected   = []

    # Table pipeline definitions 
    pipeline = [
        {
            "file":    os.path.join(data_dir, "products.csv"),
            "table":   "products",
            "clean":   clean_products,
            "std_cat": True,
        },
        {
            "file":    os.path.join(data_dir, "supermarkets.csv"),
            "table":   "supermarkets",
            "clean":   clean_supermarkets,
            "std_cat": False,
        },
        {
            "file":    os.path.join(data_dir, "price_records.csv"),
            "table":   "price_records",
            "clean":   clean_prices,
            "std_cat": False,
        },
        {
            "file":    os.path.join(data_dir, "cpi_data.csv"),
            "table":   "cpi_data",
            "clean":   clean_cpi,
            "std_cat": False,
        },
    ]

    for step in pipeline:
        log.info(f"\n── {step['table'].upper()} ──────────────────────────")

        # 1. Extract
        raw_df = load_csv(step["file"])
        if raw_df.empty:
            log.warning(f"Skipping {step['table']} — no data loaded")
            continue

        # 2. Clean
        clean_df = step["clean"](raw_df)

        # 3. Standardize categories if applicable
        if step["std_cat"] and "category" in clean_df.columns:
            clean_df = standardize_categories(clean_df)

        # 4. Validate
        valid_df, rejected_df = validate_records(clean_df, step["table"])
        if not rejected_df.empty:
            all_rejected.append(rejected_df)
            total_rejected += len(rejected_df)

        # 5. Load
        n_loaded = load_to_sqlite(valid_df, step["table"], db_path)
        total_loaded += n_loaded

    # ── Save rejected rows ───────────────────────────────────────────────────
    if all_rejected:
        save_rejected(pd.concat(all_rejected, ignore_index=True))

    # ── Log this run ─────────────────────────────────────────────────────────
    elapsed = (datetime.now() - start_time).total_seconds()
    rejection_rate = (
        round(total_rejected / (total_loaded + total_rejected) * 100, 2)
        if (total_loaded + total_rejected) > 0 else 0.0
    )

    run_stats = {
        "run_timestamp":   start_time.isoformat(),
        "records_loaded":  total_loaded,
        "records_rejected": total_rejected,
        "rejection_rate_pct": rejection_rate,
        "runtime_seconds": round(elapsed, 2),
        "status":          "SUCCESS" if total_loaded > 0 else "FAILED",
        "database":        db_path,
    }
    log_run(run_stats)

    # Summary
    log.info("\n" + "=" * 60)
    log.info("ETL PIPELINE COMPLETE")
    log.info(f"  Records loaded   : {total_loaded:,}")
    log.info(f"  Records rejected : {total_rejected:,}")
    log.info(f"  Rejection rate   : {rejection_rate}%")
    log.info(f"  Runtime          : {elapsed:.2f}s")
    log.info(f"  Database         : {db_path}")
    log.info("=" * 60)

    return run_stats


# ENTRY POINT

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MasrRetail ETL Pipeline")
    parser.add_argument("--db",       default=DEFAULT_DB_PATH,  help="SQLite database path")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="Folder containing CSV source files")
    args = parser.parse_args()

    result = run_pipeline(data_dir=args.data_dir, db_path=args.db)
    sys.exit(0 if result["status"] == "SUCCESS" else 1)
