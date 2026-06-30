import pytest
import pandas as pd
import numpy as np
from datetime import date

from etl import (
    clean_prices,
    clean_products,
    clean_supermarkets,
    clean_cpi,
    standardize_categories,
    validate_records,
)



def make_price_row(**kwargs):
    defaults = {
        "price_id":       1,
        "product_id":     1,
        "supermarket_id": 1,
        "price_egp":      50.0,
        "discount_price": None,
        "is_on_sale":     False,
        "recorded_date":  "2025-01-01",
        "source":         "carrefour_app",
        "load_timestamp": "2025-01-01 08:00:00",
    }
    defaults.update(kwargs)
    return pd.DataFrame([defaults])


def make_product_row(**kwargs):
    defaults = {
        "product_id":   1,
        "product_name": "Full Fat Milk 1L",
        "brand":        "Juhayna",
        "category":     "Dairy",
        "sub_category": "Milk",
        "unit":         "litre",
    }
    defaults.update(kwargs)
    return pd.DataFrame([defaults])


def make_supermarket_row(**kwargs):
    defaults = {
        "supermarket_id": 1,
        "chain_name":     "Carrefour",
        "branch_name":    "City Stars",
        "governorate":    "Cairo",
        "district":       "Nasr City",
        "store_type":     "Hypermarket",
        "is_active":      True,
    }
    defaults.update(kwargs)
    return pd.DataFrame([defaults])


def make_cpi_row(**kwargs):
    defaults = {
        "cpi_id":        1,
        "category":      "Food & Beverages",
        "governorate":   "National",
        "cpi_value":     215.0,
        "base_year":     2020,
        "period_year":   2025,
        "period_month":  1,
        "source_agency": "CAPMAS",
    }
    defaults.update(kwargs)
    return pd.DataFrame([defaults])


# TESTS: clean_prices()

class TestCleanPrices:

    def test_normal_row_passes_unchanged(self):
        df = make_price_row(price_egp=50.0)
        result = clean_prices(df)
        assert result["price_egp"].iloc[0] == 50.0

    def test_price_string_converted_to_float(self):
        """price_egp arriving as string "45.50" must become float 45.5"""
        df = make_price_row(price_egp="45.50")
        result = clean_prices(df)
        assert result["price_egp"].iloc[0] == 45.5
        assert result["price_egp"].dtype == float

    def test_non_numeric_price_becomes_nan(self):
        """Garbage price like 'N/A' must become NaN (validation will reject it)"""
        df = make_price_row(price_egp="N/A")
        result = clean_prices(df)
        assert pd.isna(result["price_egp"].iloc[0])

    def test_recorded_date_parsed_to_datetime(self):
        df = make_price_row(recorded_date="2025-03-15")
        result = clean_prices(df)
        assert pd.api.types.is_datetime64_any_dtype(result["recorded_date"])

    def test_invalid_date_becomes_nat(self):
        df = make_price_row(recorded_date="not-a-date")
        result = clean_prices(df)
        assert pd.isna(result["recorded_date"].iloc[0])

    def test_is_on_sale_null_filled_with_false(self):
        df = make_price_row(is_on_sale=None)
        result = clean_prices(df)
        assert result["is_on_sale"].iloc[0] == False

    def test_discount_price_cleared_when_not_on_sale(self):
        """If is_on_sale=False, discount_price must be set to NaN regardless"""
        df = make_price_row(is_on_sale=False, discount_price=35.0)
        result = clean_prices(df)
        assert pd.isna(result["discount_price"].iloc[0])

    def test_discount_price_kept_when_on_sale(self):
        df = make_price_row(is_on_sale=True, discount_price=35.0)
        result = clean_prices(df)
        assert result["discount_price"].iloc[0] == 35.0

    def test_whitespace_stripped_from_source(self):
        df = make_price_row(source="  carrefour_app  ")
        result = clean_prices(df)
        assert result["source"].iloc[0] == "carrefour_app"

    def test_empty_dataframe_returns_empty(self):
        result = clean_prices(pd.DataFrame())
        assert result.empty


# TESTS: clean_products()

class TestCleanProducts:

    def test_normal_row_passes(self):
        df = make_product_row()
        result = clean_products(df)
        assert len(result) == 1

    def test_unit_lowercased(self):
        df = make_product_row(unit="LITRE")
        result = clean_products(df)
        assert result["unit"].iloc[0] == "litre"

    def test_whitespace_stripped_from_product_name(self):
        df = make_product_row(product_name="  Full Fat Milk 1L  ")
        result = clean_products(df)
        assert result["product_name"].iloc[0] == "Full Fat Milk 1L"

    def test_empty_dataframe_returns_empty(self):
        assert clean_products(pd.DataFrame()).empty


# TESTS: clean_supermarkets()

class TestCleanSupermarkets:

    def test_store_type_title_cased(self):
        df = make_supermarket_row(store_type="hypermarket")
        result = clean_supermarkets(df)
        assert result["store_type"].iloc[0] == "Hypermarket"

    def test_is_active_null_filled_with_true(self):
        df = make_supermarket_row(is_active=None)
        result = clean_supermarkets(df)
        assert result["is_active"].iloc[0] == True

    def test_whitespace_stripped_from_chain_name(self):
        df = make_supermarket_row(chain_name="  Carrefour  ")
        result = clean_supermarkets(df)
        assert result["chain_name"].iloc[0] == "Carrefour"

    def test_empty_dataframe_returns_empty(self):
        assert clean_supermarkets(pd.DataFrame()).empty


# TESTS: clean_cpi()

class TestCleanCpi:

    def test_cpi_value_string_to_float(self):
        df = make_cpi_row(cpi_value="215.5")
        result = clean_cpi(df)
        assert result["cpi_value"].iloc[0] == 215.5

    def test_period_month_string_to_int(self):
        df = make_cpi_row(period_month="6")
        result = clean_cpi(df)
        assert result["period_month"].iloc[0] == 6

    def test_whitespace_stripped_from_category(self):
        df = make_cpi_row(category="  Food & Beverages  ")
        result = clean_cpi(df)
        assert result["category"].iloc[0] == "Food & Beverages"

    def test_empty_dataframe_returns_empty(self):
        assert clean_cpi(pd.DataFrame()).empty


# TESTS: standardize_categories()

class TestStandardizeCategories:

    def test_dairy_lowercase_maps_to_Dairy(self):
        df = make_product_row(category="dairy")
        result = standardize_categories(df)
        assert result["category"].iloc[0] == "Dairy"

    def test_meat_maps_to_meat_and_poultry(self):
        df = make_product_row(category="meat")
        result = standardize_categories(df)
        assert result["category"].iloc[0] == "Meat & Poultry"

    def test_bread_maps_to_bread_and_bakery(self):
        df = make_product_row(category="bread")
        result = standardize_categories(df)
        assert result["category"].iloc[0] == "Bread & Bakery"

    def test_vegetables_maps_correctly(self):
        df = make_product_row(category="vegetable")
        result = standardize_categories(df)
        assert result["category"].iloc[0] == "Vegetables"

    def test_oil_maps_to_packaged_goods(self):
        df = make_product_row(category="oil")
        result = standardize_categories(df)
        assert result["category"].iloc[0] == "Packaged Goods"

    def test_unknown_category_left_unchanged(self):
        df = make_product_row(category="Electronics")
        result = standardize_categories(df)
        assert result["category"].iloc[0] == "Electronics"

    def test_already_correct_category_unchanged(self):
        df = make_product_row(category="Dairy")
        result = standardize_categories(df)
        assert result["category"].iloc[0] == "Dairy"

    def test_mixed_case_mapped_correctly(self):
        df = make_product_row(category="DAIRY")
        result = standardize_categories(df)
        assert result["category"].iloc[0] == "Dairy"


# TESTS: validate_records() — price_records
class TestValidatePriceRecords:

    def test_valid_row_passes(self):
        df = clean_prices(make_price_row())
        valid, rejected = validate_records(df, "price_records")
        assert len(valid) == 1
        assert len(rejected) == 0

    def test_null_price_rejected(self):
        df = clean_prices(make_price_row(price_egp=None))
        valid, rejected = validate_records(df, "price_records")
        assert len(valid) == 0
        assert "price_egp is null" in rejected["rejection_reason"].iloc[0]

    def test_zero_price_rejected(self):
        df = clean_prices(make_price_row(price_egp=0))
        valid, rejected = validate_records(df, "price_records")
        assert len(valid) == 0
        assert "zero or negative" in rejected["rejection_reason"].iloc[0]

    def test_negative_price_rejected(self):
        df = clean_prices(make_price_row(price_egp=-10.0))
        valid, rejected = validate_records(df, "price_records")
        assert len(valid) == 0

    def test_corrupt_price_above_max_rejected(self):
        """Prices above 10,000 EGP are flagged as corrupt data"""
        df = clean_prices(make_price_row(price_egp=422020.0))
        valid, rejected = validate_records(df, "price_records")
        assert len(valid) == 0
        assert "corrupt" in rejected["rejection_reason"].iloc[0]

    def test_null_product_id_rejected(self):
        df = clean_prices(make_price_row(product_id=None))
        valid, rejected = validate_records(df, "price_records")
        assert len(valid) == 0
        assert "product_id is null" in rejected["rejection_reason"].iloc[0]

    def test_null_supermarket_id_rejected(self):
        df = clean_prices(make_price_row(supermarket_id=None))
        valid, rejected = validate_records(df, "price_records")
        assert len(valid) == 0

    def test_null_date_rejected(self):
        df = clean_prices(make_price_row(recorded_date="not-a-date"))
        valid, rejected = validate_records(df, "price_records")
        assert len(valid) == 0
        assert "recorded_date" in rejected["rejection_reason"].iloc[0]

    def test_duplicate_rows_second_one_rejected(self):
        """Same product + store + date twice → second row rejected"""
        row = clean_prices(make_price_row())
        df = pd.concat([row, row], ignore_index=True)
        valid, rejected = validate_records(df, "price_records")
        assert len(valid) == 1
        assert len(rejected) == 1
        assert "duplicate" in rejected["rejection_reason"].iloc[0]

    def test_rejected_row_has_reason_column(self):
        df = clean_prices(make_price_row(price_egp=None))
        _, rejected = validate_records(df, "price_records")
        assert "rejection_reason" in rejected.columns

    def test_rejected_row_has_source_table_column(self):
        df = clean_prices(make_price_row(price_egp=None))
        _, rejected = validate_records(df, "price_records")
        assert rejected["source_table"].iloc[0] == "price_records"


# TESTS: validate_records() — products

class TestValidateProducts:

    def test_valid_product_passes(self):
        df = clean_products(make_product_row())
        valid, rejected = validate_records(df, "products")
        assert len(valid) == 1
        assert len(rejected) == 0

    def test_null_product_name_rejected(self):
        df = clean_products(make_product_row(product_name=None))
        valid, rejected = validate_records(df, "products")
        assert len(valid) == 0

    def test_null_category_rejected(self):
        df = clean_products(make_product_row(category=None))
        valid, rejected = validate_records(df, "products")
        assert len(valid) == 0


# TESTS: validate_records() — supermarkets

class TestValidateSupermarkets:

    def test_valid_supermarket_passes(self):
        df = clean_supermarkets(make_supermarket_row())
        valid, rejected = validate_records(df, "supermarkets")
        assert len(valid) == 1

    def test_null_chain_name_rejected(self):
        df = clean_supermarkets(make_supermarket_row(chain_name=None))
        valid, rejected = validate_records(df, "supermarkets")
        assert len(valid) == 0

    def test_null_governorate_rejected(self):
        df = clean_supermarkets(make_supermarket_row(governorate=None))
        valid, rejected = validate_records(df, "supermarkets")
        assert len(valid) == 0


# TESTS: validate_records() — cpi_data

class TestValidateCpi:

    def test_valid_cpi_row_passes(self):
        df = clean_cpi(make_cpi_row())
        valid, rejected = validate_records(df, "cpi_data")
        assert len(valid) == 1

    def test_null_cpi_value_rejected(self):
        df = clean_cpi(make_cpi_row(cpi_value=None))
        valid, rejected = validate_records(df, "cpi_data")
        assert len(valid) == 0

    def test_zero_cpi_value_rejected(self):
        df = clean_cpi(make_cpi_row(cpi_value=0))
        valid, rejected = validate_records(df, "cpi_data")
        assert len(valid) == 0

    def test_month_13_rejected(self):
        df = clean_cpi(make_cpi_row(period_month=13))
        valid, rejected = validate_records(df, "cpi_data")
        assert len(valid) == 0
        assert "period_month" in rejected["rejection_reason"].iloc[0]

    def test_month_0_rejected(self):
        df = clean_cpi(make_cpi_row(period_month=0))
        valid, rejected = validate_records(df, "cpi_data")
        assert len(valid) == 0

    def test_valid_months_1_to_12_all_pass(self):
        rows = [make_cpi_row(cpi_id=i, period_month=i) for i in range(1, 13)]
        df = clean_cpi(pd.concat(rows, ignore_index=True))
        valid, rejected = validate_records(df, "cpi_data")
        assert len(valid) == 12
        assert len(rejected) == 0

    def test_null_category_rejected(self):
        df = clean_cpi(make_cpi_row(category=None))
        valid, rejected = validate_records(df, "cpi_data")
        assert len(valid) == 0
