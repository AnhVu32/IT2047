"""Finalize cleaned dataset by removing outliers for each property type.

This step applies tailored residential boundaries for apartments (Can ho)
and houses/land (Nha dat) to produce a predictable, reliable dataset for
price forecasting.
"""

from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_FILE = SCRIPT_DIR.parent / "step-2/cleaned_data.xlsx"
OUTPUT_FILE = SCRIPT_DIR / "outliers_removed.xlsx"

# Tailored boundaries for each property type
APARTMENT_RULES = {
    "min_area": 25,
    "max_area": 150,
    "min_beds": 1,
    "max_beds": 4,
    "min_price": 1.0,
    "max_price": 20.0,
    "min_price_m2": 20,
    "max_price_m2": 180,
}

HOUSE_RULES = {
    "min_area": 20,
    "max_area": 350,
    "min_beds": 1,
    "max_beds": 8,
    "min_price": 1.5,
    "max_price": 40.0,
    "min_price_m2": 30,
    "max_price_m2": 350,
}


def filter_subset(df: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """Filter records within specified residential boundaries."""
    unit_price = (df["price_range"] * 1000) / df["area"]

    valid_mask = (
        df["area"].between(rules["min_area"], rules["max_area"])
        & df["bedrooms"].between(rules["min_beds"], rules["max_beds"])
        & df["price_range"].between(rules["min_price"], rules["max_price"])
        & unit_price.between(rules["min_price_m2"], rules["max_price_m2"])
    )
    return df.loc[valid_mask].copy()


def remove_outliers(source: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """Separate by property type, filter outliers, and combine results."""
    apartments = source[source["property_type"] == "Căn hộ"]
    houses = source[source["property_type"] == "Nhà đất"]

    clean_apartments = filter_subset(apartments, APARTMENT_RULES)
    clean_houses = filter_subset(houses, HOUSE_RULES)

    apt_dropped = len(apartments) - len(clean_apartments)
    house_dropped = len(houses) - len(clean_houses)

    combined = pd.concat([clean_apartments, clean_houses], ignore_index=True)
    return combined, apt_dropped, house_dropped


def main() -> None:
    source = pd.read_excel(INPUT_FILE, dtype={"listing_id": "string"})

    output, apt_dropped, house_dropped = remove_outliers(source)
    output.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")

    total_dropped = apt_dropped + house_dropped
    print(f"Input:  {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Rows: {len(source):,} -> {len(output):,}")
    print(f"Removed apartment outliers: {apt_dropped:,}")
    print(f"Removed house/land outliers: {house_dropped:,}")
    print(f"Total outliers removed: {total_dropped:,}")
    print("Missing values after Step 3:")
    for column, count in output.isna().sum().items():
        if count:
            print(f"  - {column}: {count:,}")


if __name__ == "__main__":
    main()
