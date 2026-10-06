"""Encode categoricals, engineer features, and apply log-transformed pricing.

Steps:
1. Engineer `area_per_bedroom = area / bedrooms`.
2. Apply log pricing: `log_price = np.log1p(price_range)`.
3. One-hot encode categorical features: `property_type`, `legal_status`, `district`.
4. Preserve `listing_id` for tracking and downstream splits.
"""

from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_FILE = SCRIPT_DIR.parent / "step-3/outliers_removed.xlsx"
OUTPUT_FILE = SCRIPT_DIR / "encoded_data.xlsx"


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived numerical features and log-transformed target."""
    result = df.copy()

    # Derived feature: living space per bedroom
    result["area_per_bedroom"] = (result["area"] / result["bedrooms"]).round(2)

    # Log-transformed price target
    result["log_price"] = np.log1p(result["price_range"]).round(4)
    result = result.drop(columns=["price_range"])

    return result


def encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encode categorical features and order columns cleanly."""
    categorical_columns = ["property_type", "legal_status", "district"]
    encoded = pd.get_dummies(df, columns=categorical_columns, dtype=int)

    # Clean column order: identifier -> numeric features -> encoded categories -> target
    numeric_columns = [
        "listing_id",
        "area",
        "bedrooms",
        "area_per_bedroom",
        "latitude",
        "longitude",
    ]
    encoded_columns = [
        col for col in encoded.columns if col not in numeric_columns and col != "log_price"
    ]
    ordered_columns = numeric_columns + encoded_columns + ["log_price"]

    return encoded[ordered_columns]


def main() -> None:
    source = pd.read_excel(INPUT_FILE, dtype={"listing_id": "string"})

    featured = add_features(source)
    output = encode_categoricals(featured)

    output.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")

    print(f"Input:  {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Rows:   {len(output):,}; Columns: {len(output.columns):,}")
    print("Features summary:")
    print("  - Preserved identifier: listing_id")
    print("  - Added feature:        area_per_bedroom")
    print("  - Target variable:      log_price (log1p of price_range)")
    print(f"  - Encoded categories:   {len(output.columns) - 7} one-hot columns")
    print(f"  - Total missing values: {output.isna().sum().sum()}")


if __name__ == "__main__":
    main()
