# MasrRetail ETL

[![Run ETL Tests](https://github.com/reemy-y/MasrRetail-ETL/actions/workflows/tests.yml/badge.svg)](https://github.com/reemy-y/MasrRetail-ETL/actions/workflows/tests.yml)

A data pipeline and interactive dashboard that tracks grocery prices across Egyptian supermarket chains and benchmarks them against official CAPMAS inflation data (CPI).

**Live demo:** [https://masr-retail.streamlit.app/](https://masr-retail.streamlit.app/)

---

## System requirements

| Requirement | Details |
|---|---|
| Python | 3.10 or higher (developed and tested on 3.12) |
| Operating system | Windows, macOS, or Linux — no OS-specific dependencies |
| RAM | 2 GB minimum (the SQLite database is under 5 MB; no heavy in-memory processing) |
| Disk space | ~50 MB for the repo, dependencies, and generated database |
| Internet connection | Only required once, to install dependencies via pip (no internet needed at runtime — all data is local) |

No GPU, external database server, or paid API key is required. Everything runs on a single machine using local CSV files and SQLite.

---

## Configuration

This project requires no environment variables, API keys, or config files. All settings (file paths, validation thresholds) are defined as constants at the top of `etl.py` and `app.py`. To change the data source folder or output database path, either edit those constants directly or pass command-line arguments to `etl.py`:

```bash
python etl.py --data-dir path/to/your/csvs --db path/to/output.db
```

---

## API documentation

This project does not expose or consume any external API. All data is read from local CSV files and a local SQLite database — there is no client-server API layer.

---

## Executable files

This is a Python web application, not a compiled desktop or mobile app — there is no `.exe`, `.jar`, or `.apk` file. It runs as a Streamlit web app, accessible either:

- **Live, with no installation:** [https://masr-retail.streamlit.app/](https://masr-retail.streamlit.app/)
- **Locally,** by following Option B in the Execution guide below

---

## What this project does

MasrRetail collects grocery prices from multiple Egyptian supermarket chains across 17 governorates, cleans and validates the data through an ETL pipeline, stores it in a relational SQLite database, and visualizes it through a Streamlit dashboard — allowing direct comparison between real supermarket price trends and Egypt's official Consumer Price Index (CPI).

The core question this project answers: **are grocery prices rising faster or slower than official inflation?**

---

## Features

- **Price Trends** — track any product's average price over time (Jan 2024 – Jun 2026), with an optional CPI overlay to compare against official inflation
- **Cross-Retailer Comparison** — see the latest price for any product across every store, sorted cheapest to most expensive, with the lowest price highlighted
- **Overview** — dataset summary stats, average price by category and by chain, and a raw table browser for all 4 underlying tables
- **Pipeline Log** — view every ETL run's status, records loaded/rejected, and rejection rate; inspect any rejected rows and why they failed validation
- Every table in the dashboard has a CSV export button
- Filterable by category, product, governorate, and supermarket chain

---

## Project structure

```
MasrRetail/
├── .github/
│   └── workflows/
│       └── tests.yml          # GitHub Actions CI — runs ETL + pytest on every push/PR
├── masrretail_data/           # Source CSVs (input to the ETL pipeline)
│   ├── products.csv           # 50 grocery products across 5 categories
│   ├── supermarkets.csv       # 40 store branches across 17 governorates, 6 chains
│   ├── price_records.csv      # ~45,600 price observations (Jan 2024 – Jun 2026)
│   ├── cpi_data.csv           # ~1,944 CAPMAS CPI records (2022–2026)
│   └── governorates.csv       # Reference table of Egypt's 27 governorates
├── etl.py                     # ETL pipeline: extract, clean, validate, load
├── test_etl.py                # pytest unit tests for every ETL function
├── app.py                     # Streamlit dashboard
├── requirements.txt           # Python dependencies
└── README.md
```

Running `etl.py` generates two additional files used by the dashboard's Pipeline Log tab:
- `masrretail.db` — the SQLite database
- `etl_run_log.csv` — a log of every pipeline run
- `rejected_rows.csv` — rows that failed validation, if any

---

## Tech stack

| Tool | Purpose |
|---|---|
| Python 3.12 | Core language |
| pandas | Data cleaning and transformation |
| SQLite | Relational database |
| Streamlit | Dashboard UI |
| Plotly | Interactive charts |
| pytest | Unit testing |

---

## Database schema

Four tables, related by foreign keys:

- **`products`** — product catalog (name, brand, category, sub-category, unit)
- **`supermarkets`** — store branches (chain, branch name, governorate, district, store type)
- **`price_records`** — the core fact table: one row per product × store × month, with price, discount price, and sale flag
- **`cpi_data`** — official CAPMAS Consumer Price Index by category, governorate, and month

`price_records` references both `products` and `supermarkets` by foreign key, enabling cross-retailer and cross-category analysis.

---

## Version control & collaboration

**Repository:** [github.com/reemy-y/MasrRetail-ETL](https://github.com/reemy-y/MasrRetail-ETL) (public)

### Branching strategy

This project follows a lightweight **Feature Branching** workflow:

- `main` — always holds the current stable, working version of the app
- `feature/<short-description>` — new features or fixes are developed in a dedicated branch (e.g. `feature/cpi-category-mapping`, `feature/expand-governorates`) and merged into `main` via a pull request once tested
- Direct commits to `main` are reserved for documentation-only changes (e.g. README updates)

Each pull request is reviewed against the test suite (see CI/CD below) before merging, ensuring `main` never breaks.

### Commit history & documentation

Commit messages follow a short imperative style describing what changed and why (e.g. `Fix CPI overlay category mismatch`, `Stop tracking generated database and log files`). Larger changes — such as expanding the dataset from 20 to 40 supermarket branches — are documented in the commit body or accompanying pull request description, explaining the reasoning and the before/after impact.

### CI/CD integration

This repo uses **GitHub Actions** for continuous integration. On every push and pull request targeting `main`, the workflow defined in [`.github/workflows/tests.yml`](.github/workflows/tests.yml) automatically:

1. Checks out the repo and sets up Python 3.12
2. Installs all dependencies from `requirements.txt`
3. Runs the full ETL pipeline as a sanity check (confirms the pipeline still builds a valid database from the current CSVs)
4. Runs the full 54-test pytest suite

If either step fails, the pull request is flagged and should not be merged until fixed. The current build status is shown in the badge at the top of this README.

## Execution guide

### Option A — Use the deployed version (no installation needed)

Visit [https://masr-retail.streamlit.app/](https://masr-retail.streamlit.app/). The dashboard loads with all data pre-built — no setup required.

### Option B — Run it locally

#### 1. Clone the repo
```bash
git clone https://github.com/reemy-y/MasrRetail-ETL.git
cd MasrRetail-ETL
```

#### 2. Install dependencies
```bash
pip install -r requirements.txt
```

#### 3. Run the ETL pipeline
```bash
python etl.py
```
This reads all 5 CSVs from `masrretail_data/`, cleans and validates every row, and loads the result into `masrretail.db`. Safe to re-run any time — it upserts rather than duplicating records.

#### 4. Run the tests
```bash
pytest test_etl.py -v
```
54 unit tests covering every cleaning, standardization, and validation function.

#### 5. Launch the dashboard
```bash
streamlit run app.py
```
Opens automatically at `http://localhost:8501`.

---

## ETL pipeline details

`etl.py` follows a standard Extract → Clean → Standardize → Validate → Load pattern:

1. **Extract** — reads each CSV with pandas, handling missing files gracefully
2. **Clean** — strips whitespace, coerces data types, parses dates, fills sensible defaults
3. **Standardize** — maps inconsistent category names (e.g. "dairy", "milk") to 5 standard categories
4. **Validate** — rejects rows with null/zero/negative prices, prices above a sanity threshold, missing foreign keys, invalid dates, duplicate records, and out-of-range CPI months. Every rejected row is logged with a specific reason to `rejected_rows.csv`
5. **Load** — writes validated rows into SQLite using `INSERT OR REPLACE`, so re-running the pipeline updates existing records instead of crashing on duplicate keys

Each pipeline run appends a summary row to `etl_run_log.csv` (timestamp, records loaded, records rejected, rejection rate, runtime), which the dashboard's Pipeline Log tab reads directly.

---

## Data sources

- **Supermarket prices** — manually collected from Carrefour, Spinneys, Kheir Zaman, Seoudi, Hyperone, and Metro Market across 17 Egyptian governorates
- **CPI data** — [CAPMAS (Central Agency for Public Mobilization and Statistics)](https://www.capmas.gov.eg/Pages/StaticPages.aspx?page_id=5036), Egypt's official statistics agency

---

## Deployment notes (for redeploying or forking)

This app is deployed on **Streamlit Community Cloud** at [https://masr-retail.streamlit.app/](https://masr-retail.streamlit.app/). To deploy your own copy after forking:

1. Push the repo to your own GitHub account
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click **New app**, select your fork, branch `main`, and main file path `app.py`
4. Click **Deploy**

`app.py` automatically builds `masrretail.db` from the CSVs in `masrretail_data/` on first launch if the database doesn't already exist — no manual setup step is needed on the cloud.

---

## Team

Reem Yasser Mohamed-
Reem Osama Mohamed-
Mai Ahmed Mostafa-
Joussiana Atef Marzouk

---

## License

This project was built for academic purposes as part of a graduation requirement.
