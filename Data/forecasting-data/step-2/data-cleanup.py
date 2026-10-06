"""Clean unreliable records and fields for price forecasting.

The bounds cover the expanded Ho Chi Minh City area, including the former
Binh Duong and Ba Ria - Vung Tau areas. They are a coarse validation box, not
an administrative-boundary polygon.
"""

from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_FILE = SCRIPT_DIR.parent / "step-1/reliable_features.xlsx"
OUTPUT_FILE = SCRIPT_DIR / "cleaned_data.xlsx"

MIN_LATITUDE = 10.3
MAX_LATITUDE = 11.6
MIN_LONGITUDE = 106.3
MAX_LONGITUDE = 107.6


def duplicate_records_filter(source: pd.DataFrame) -> pd.DataFrame:
    """Keep the first record for each listing ID."""
    if "listing_id" not in source:
        raise ValueError("Missing required column: listing_id")

    return source.drop_duplicates(subset=["listing_id"], keep="first").reset_index(
        drop=True
    )


def coordinates_filter(source: pd.DataFrame) -> pd.DataFrame:
    """Return rows with numeric coordinates inside the HCMC bounding box."""
    required_columns = ["latitude", "longitude"]
    missing_columns = [column for column in required_columns if column not in source]
    if missing_columns:
        raise ValueError(f"Missing required coordinate columns: {missing_columns}")

    result = source.copy()
    result["latitude"] = pd.to_numeric(result["latitude"], errors="coerce")
    result["longitude"] = pd.to_numeric(result["longitude"], errors="coerce")

    valid_coordinates = (
        result["latitude"].between(MIN_LATITUDE, MAX_LATITUDE)
        & result["longitude"].between(MIN_LONGITUDE, MAX_LONGITUDE)
    )
    return result.loc[valid_coordinates].reset_index(drop=True)


def bedrooms_filter(source: pd.DataFrame) -> pd.DataFrame:
    """Return rows that contain bedroom information."""
    if "bedrooms" not in source:
        raise ValueError("Missing required column: bedrooms")

    return source.dropna(subset=["bedrooms"]).reset_index(drop=True)


def remove_furnishing(source: pd.DataFrame) -> pd.DataFrame:
    """Remove the unreliable furnishing field."""
    if "furnishing" not in source:
        raise ValueError("Missing required column: furnishing")

    return source.drop(columns=["furnishing"])


def main() -> None:
    source = pd.read_excel(INPUT_FILE, dtype={"listing_id": "string"})
    unique_records = duplicate_records_filter(source)
    valid_coordinates = coordinates_filter(unique_records)
    complete_bedrooms = bedrooms_filter(valid_coordinates)
    output = remove_furnishing(complete_bedrooms)
    output.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")

    print(f"Input:  {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Rows: {len(source):,} -> {len(output):,}")
    print(f"Removed as duplicates: {len(source) - len(unique_records):,}")
    print(f"Removed for invalid coordinates: {len(unique_records) - len(valid_coordinates):,}")
    print(f"Removed for missing bedrooms: {len(valid_coordinates) - len(complete_bedrooms):,}")
    print("Removed column: furnishing")
    print("Missing values after Step 2:")
    for column, count in output.isna().sum().items():
        if count:
            print(f"  - {column}: {count:,}")


if __name__ == "__main__":
    main()
