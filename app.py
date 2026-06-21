
import os
import sqlite3
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# CONFIG

DB_PATH = "masrretail.db"
RUN_LOG_PATH = "etl_run_log.csv"
REJECTED_PATH = "rejected_rows.csv"

st.set_page_config(
    page_title="MasrRetail | Grocery Price Tracker",
    page_icon=":shopping_trolley:",
    layout="wide",
)

# Fix for blurry dropdown list rendering in some Chrome/Edge + Windows combos.
# Only disable font smoothing/backdrop-filter — leave transform/positioning alone
# so Streamlit's own logic for flipping the dropdown up/down still works.
st.markdown("""
    <style>
    div[data-baseweb="popover"] ul[role="listbox"] li {
        backdrop-filter: none !important;
        -webkit-font-smoothing: antialiased;
    }
    </style>
""", unsafe_allow_html=True)

# DATA LOADING 

@st.cache_data(ttl=300)
def load_table(query: str) -> pd.DataFrame:
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(query, conn)


@st.cache_data(ttl=300)
def get_filter_options():
    products = load_table("SELECT product_id, product_name, category FROM products ORDER BY product_name")
    govs = load_table("SELECT DISTINCT governorate FROM supermarkets ORDER BY governorate")
    chains = load_table("SELECT DISTINCT chain_name FROM supermarkets ORDER BY chain_name")
    categories = load_table("SELECT DISTINCT category FROM products ORDER BY category")
    return products, govs, chains, categories


def to_csv_download(df: pd.DataFrame, label: str, filename: str, key: str):
    """Reusable CSV download button for any table."""
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(label, csv, filename, "text/csv", key=key)



# AUTO-RUN ETL on first launch 

if not os.path.exists(DB_PATH):
    with st.spinner("First-time setup: running ETL pipeline to build the database..."):
        from etl import run_pipeline
        try:
            run_pipeline(data_dir="masrretail_data", db_path=DB_PATH)
        except Exception as e:
            st.error(
                f"ETL pipeline failed to run automatically: {e}\n\n"
                "Try running it manually:\n```\npython etl.py\n```"
            )
            st.stop()

if not os.path.exists(DB_PATH):
    st.error(
        f"Database still not found at `{DB_PATH}` after running the pipeline.\n\n"
        "Check that the `masrretail_data/` folder with all 5 CSVs is present in the repo."
    )
    st.stop()

products_df, gov_df, chain_df, category_df = get_filter_options()

if products_df.empty:
    st.error("Database is empty. Run `python etl.py` to load data first.")
    st.stop()

# SIDEBAR — Filters

st.sidebar.title("MasrRetail")
st.sidebar.caption("Grocery price tracking vs official CPI")

st.sidebar.header("Filters")

selected_category = st.sidebar.selectbox(
    "Category",
    options=["All"] + category_df["category"].tolist(),
)

filtered_products = products_df if selected_category == "All" else products_df[products_df["category"] == selected_category]

selected_product = st.sidebar.selectbox(
    "Product",
    options=filtered_products["product_name"].tolist(),
    index=0 if len(filtered_products) > 0 else None,
)

selected_govs = st.sidebar.multiselect(
    "Governorate",
    options=gov_df["governorate"].tolist(),
    default=gov_df["governorate"].tolist(),
)

selected_chains = st.sidebar.multiselect(
    "Supermarket chain",
    options=chain_df["chain_name"].tolist(),
    default=chain_df["chain_name"].tolist(),
)

show_cpi_overlay = st.sidebar.checkbox("Show CPI overlay on trend chart", value=True)

st.sidebar.markdown("---")
st.sidebar.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M')}")


# HEADER

st.title("MasrRetail — Egypt Grocery Price Tracker")
st.caption("Comparing supermarket prices across Egypt against official CAPMAS inflation data")

if not selected_govs or not selected_chains:
    st.warning("Select at least one governorate and one chain from the sidebar to see data.")
    st.stop()

gov_list_sql = "', '".join(selected_govs)
chain_list_sql = "', '".join(selected_chains)

# TABS

tab1, tab2, tab3, tab4 = st.tabs([
    "Price Trends", "Cross-Retailer Comparison", "Overview", "Pipeline Log"
])

# TAB 1

with tab1:
    st.subheader(f"Price trend: {selected_product}")

    trend_query = f"""
        SELECT p.recorded_date, p.price_egp, s.chain_name, s.governorate
        FROM price_records p
        JOIN products prod ON p.product_id = prod.product_id
        JOIN supermarkets s ON p.supermarket_id = s.supermarket_id
        WHERE prod.product_name = '{selected_product}'
          AND s.governorate IN ('{gov_list_sql}')
          AND s.chain_name IN ('{chain_list_sql}')
        ORDER BY p.recorded_date
    """
    trend_df = load_table(trend_query)

    if trend_df.empty:
        st.info("No price data for this combination of filters.")
    else:
        trend_df["recorded_date"] = pd.to_datetime(trend_df["recorded_date"])
        monthly_avg = trend_df.groupby("recorded_date", as_index=False)["price_egp"].mean()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=monthly_avg["recorded_date"], y=monthly_avg["price_egp"],
            mode="lines+markers", name="Avg. Price (EGP)",
            line=dict(color="#2E7D32", width=3),
        ))

        if show_cpi_overlay:
            product_category = products_df.loc[
                products_df["product_name"] == selected_product, "category"
            ].iloc[0]

            # Product categories and CPI categories use different naming conventions.
            # Map product category -> matching CPI category before querying.
            PRODUCT_TO_CPI_CATEGORY = {
                "Bread & Bakery":  "Bread & Cereals",
                "Dairy":           "Dairy",
                "Meat & Poultry":  "Meat & Poultry",
                "Vegetables":      "Vegetables",
                "Packaged Goods":  "Food & Beverages",
            }
            cpi_category = PRODUCT_TO_CPI_CATEGORY.get(product_category, product_category)

            # Only plot CPI points within the same date range as the price data,
            # so the chart's x-axis doesn't extend further back than actual prices.
            min_price_date = trend_df["recorded_date"].min()

            cpi_query = f"""
                SELECT period_year, period_month, AVG(cpi_value) as cpi_value
                FROM cpi_data
                WHERE category = '{cpi_category}' AND governorate = 'National'
                  AND (period_year > {min_price_date.year}
                       OR (period_year = {min_price_date.year} AND period_month >= {min_price_date.month}))
                GROUP BY period_year, period_month
                ORDER BY period_year, period_month
            """
            cpi_df = load_table(cpi_query)
            if not cpi_df.empty:
                cpi_df["date"] = pd.to_datetime(
                    cpi_df["period_year"].astype(str) + "-" + cpi_df["period_month"].astype(str) + "-01"
                )
                fig.add_trace(go.Scatter(
                    x=cpi_df["date"], y=cpi_df["cpi_value"],
                    mode="lines", name=f"CPI: {cpi_category} (National)",
                    line=dict(color="#C62828", width=2, dash="dash"),
                    yaxis="y2",
                ))
                fig.update_layout(
                    yaxis2=dict(title="CPI Index (Base 2020=100)", overlaying="y", side="right")
                )
            else:
                st.caption(f"No CPI data available for category '{cpi_category}'.")

        fig.update_layout(
            xaxis_title="Date", yaxis_title="Price (EGP)",
            hovermode="x unified", height=480,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("Latest avg. price", f"{monthly_avg['price_egp'].iloc[-1]:.2f} EGP")
        pct_change = (
            (monthly_avg["price_egp"].iloc[-1] - monthly_avg["price_egp"].iloc[0])
            / monthly_avg["price_egp"].iloc[0] * 100
        )
        col2.metric("Change over period", f"{pct_change:+.1f}%")
        col3.metric("Data points", len(trend_df))

        to_csv_download(trend_df, "Download price trend data (CSV)", "price_trend.csv", "dl_trend")

# TAB 2

with tab2:
    st.subheader(f"Latest prices by retailer: {selected_product}")

    compare_query = f"""
        SELECT s.chain_name, s.branch_name, s.governorate, p.price_egp,
               p.is_on_sale, p.discount_price, p.recorded_date
        FROM price_records p
        JOIN products prod ON p.product_id = prod.product_id
        JOIN supermarkets s ON p.supermarket_id = s.supermarket_id
        WHERE prod.product_name = '{selected_product}'
          AND s.governorate IN ('{gov_list_sql}')
          AND s.chain_name IN ('{chain_list_sql}')
          AND p.recorded_date = (
              SELECT MAX(recorded_date) FROM price_records
          )
        ORDER BY p.price_egp ASC
    """
    compare_df = load_table(compare_query)

    if compare_df.empty:
        st.info("No data for this combination of filters in the latest period.")
    else:
        display_df = compare_df.copy()
        display_df["price_egp"] = display_df["price_egp"].round(2)
        display_df["discount_price"] = pd.to_numeric(display_df["discount_price"], errors="coerce").round(2)
        display_df["is_on_sale"] = display_df["is_on_sale"].map({1: "Yes", 0: "No"})
        display_df = display_df.rename(columns={
            "chain_name": "Chain", "branch_name": "Branch", "governorate": "Governorate",
            "price_egp": "Price (EGP)", "is_on_sale": "On Sale",
            "discount_price": "Discount Price", "recorded_date": "Date",
        })

        min_price = display_df["Price (EGP)"].min()

        def highlight_lowest(row):
            return ["background-color: #C8E6C9" if row["Price (EGP)"] == min_price else "" for _ in row]

        st.dataframe(
            display_df.style.apply(highlight_lowest, axis=1).format({
                "Price (EGP)": "{:.2f}",
                "Discount Price": lambda x: "" if pd.isna(x) else f"{x:.2f}",
            }),
            use_container_width=True, hide_index=True, height=350,
        )

        cheapest = display_df.loc[display_df["Price (EGP)"].idxmin()]
        st.success(f"Cheapest: **{cheapest['Chain']}** ({cheapest['Branch']}) at **{cheapest['Price (EGP)']} EGP**")

        to_csv_download(compare_df, "Download comparison data (CSV)", "retailer_comparison.csv", "dl_compare")

        # Bar chart view
        fig_bar = px.bar(
            display_df, x="Chain", y="Price (EGP)", color="Governorate",
            title=f"{selected_product} — price by chain", height=400,
        )
        st.plotly_chart(fig_bar, use_container_width=True)


# TAB 3

with tab3:
    st.subheader("Dataset overview")

    counts = {
        "Products": load_table("SELECT COUNT(*) n FROM products")["n"].iloc[0],
        "Supermarkets": load_table("SELECT COUNT(*) n FROM supermarkets")["n"].iloc[0],
        "Price records": load_table("SELECT COUNT(*) n FROM price_records")["n"].iloc[0],
        "CPI records": load_table("SELECT COUNT(*) n FROM cpi_data")["n"].iloc[0],
    }
    cols = st.columns(4)
    for col, (label, value) in zip(cols, counts.items()):
        col.metric(label, f"{value:,}")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Average price by category (latest month)**")
        cat_query = """
            SELECT prod.category, ROUND(AVG(p.price_egp),2) as avg_price
            FROM price_records p
            JOIN products prod ON p.product_id = prod.product_id
            WHERE p.recorded_date = (SELECT MAX(recorded_date) FROM price_records)
            GROUP BY prod.category ORDER BY avg_price DESC
        """
        cat_df = load_table(cat_query)
        fig_cat = px.bar(cat_df, x="category", y="avg_price", color="category")
        fig_cat.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig_cat, use_container_width=True)

    with col2:
        st.markdown("**Average price by chain (latest month)**")
        chain_query = """
            SELECT s.chain_name, ROUND(AVG(p.price_egp),2) as avg_price
            FROM price_records p
            JOIN supermarkets s ON p.supermarket_id = s.supermarket_id
            WHERE p.recorded_date = (SELECT MAX(recorded_date) FROM price_records)
            GROUP BY s.chain_name ORDER BY avg_price DESC
        """
        chain_avg_df = load_table(chain_query)
        fig_chain = px.bar(chain_avg_df, x="chain_name", y="avg_price", color="chain_name")
        fig_chain.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig_chain, use_container_width=True)

    st.markdown("---")
    st.markdown("**Browse raw tables**")
    table_choice = st.selectbox("Table", ["products", "supermarkets", "price_records", "cpi_data"])
    raw_df = load_table(f"SELECT * FROM {table_choice} LIMIT 500")
    float_cols = raw_df.select_dtypes(include="float").columns
    column_config = {col: st.column_config.NumberColumn(format="%.2f") for col in float_cols}
    st.dataframe(raw_df, use_container_width=True, hide_index=True, column_config=column_config)
    to_csv_download(raw_df, f"Download {table_choice}.csv", f"{table_choice}.csv", f"dl_{table_choice}")

# TAB 4 

with tab4:
    st.subheader("ETL pipeline run history")

    if os.path.exists(RUN_LOG_PATH):
        log_df = pd.read_csv(RUN_LOG_PATH)
        log_df = log_df.sort_values("run_timestamp", ascending=False)

        st.dataframe(
            log_df, use_container_width=True, hide_index=True,
            column_config={"rejection_rate_pct": st.column_config.NumberColumn(format="%.2f")},
        )

        latest = log_df.iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Last run status", latest["status"])
        col2.metric("Records loaded", f"{int(latest['records_loaded']):,}")
        col3.metric("Records rejected", f"{int(latest['records_rejected']):,}")
        col4.metric("Rejection rate", f"{latest['rejection_rate_pct']}%")

        to_csv_download(log_df, "Download run log (CSV)", "etl_run_log.csv", "dl_runlog")
    else:
        st.info("No run log found yet. Run `python etl.py` to generate one.")

    st.markdown("---")
    st.markdown("**Rejected rows**")
    if os.path.exists(REJECTED_PATH):
        rejected_df = pd.read_csv(REJECTED_PATH)
        float_cols = rejected_df.select_dtypes(include="float").columns
        column_config = {col: st.column_config.NumberColumn(format="%.2f") for col in float_cols}
        st.dataframe(rejected_df, use_container_width=True, hide_index=True, column_config=column_config)
        to_csv_download(rejected_df, "Download rejected rows (CSV)", "rejected_rows.csv", "dl_rejected")
    else:
        st.success("No rejected rows — all data passed validation.")

# FOOTER

st.markdown("---")
st.caption("MasrRetail ETL — Graduation project | Data: collected supermarket prices + CAPMAS CPI")
