# MasrRetail ETL

A data pipeline and interactive dashboard that tracks grocery prices across Egyptian supermarket chains and benchmarks them against official CAPMAS inflation data (CPI).

**Live demo:** _add your Streamlit Cloud link here after deploying_

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

## Running it locally

### 1. Clone the repo
```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the ETL pipeline
```bash
python etl.py
```
This reads all 5 CSVs from `masrretail_data/`, cleans and validates every row, and loads the result into `masrretail.db`. Safe to re-run any time — it upserts rather than duplicating records.

### 4. Run the tests
```bash
pytest test_etl.py -v
```
54 unit tests covering every cleaning, standardization, and validation function.

### 5. Launch the dashboard
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

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub (see below)
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click **New app**, select this repository, branch `main`, and main file path `app.py`
4. Click **Deploy**

The deployed app will run `etl.py`-generated data if `masrretail.db` is committed to the repo, or you'll need to run `etl.py` once locally and commit the resulting `.db` file so the cloud deployment has data to read.

---

## Team

Graduation project — Data Engineer track, DEPI (Digital Egypt Pioneers Initiative).

---

## License

This project was built for academic purposes as part of a graduation requirement.
