"""Create the Step 1 price-forecasting dataset from Final_Data.xlsx.

This step keeps only the fields approved in the forecasting-data README. It
does not impute missing values or repair questionable observations; later
pipeline steps can make those decisions explicitly.
"""

from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_FILE = SCRIPT_DIR.parent.parent / "Final_Data.xlsx"
OUTPUT_FILE = SCRIPT_DIR / "reliable_features.xlsx"

SOURCE_COLUMNS = [
    "listing_id",
    "property_type",
    "area",
    "latitude_longitude",
    "district",
    "bedrooms",
    "legal_status",
    "furnishing",
    "price_range",
]

OUTPUT_COLUMNS = [
    "listing_id",
    "property_type",
    "area",
    "latitude",
    "longitude",
    "district",
    "bedrooms",
    "legal_status",
    "furnishing",
    "price_range",
]

def parse_coordinates(values: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Parse strings such as ``q=10.77,106.69`` without validating location."""
    coordinates = values.astype("string").str.extract(
        r"q?\s*=\s*([-+]?\d+(?:\.\d+)?)\s*,\s*([-+]?\d+(?:\.\d+)?)"
    )
    latitude = pd.to_numeric(coordinates[0], errors="coerce")
    longitude = pd.to_numeric(coordinates[1], errors="coerce")
    return latitude, longitude


def build_reliable_dataset(source: pd.DataFrame) -> pd.DataFrame:
    """Select and minimally standardize the approved forecasting fields."""
    missing_columns = [column for column in SOURCE_COLUMNS if column not in source]
    if missing_columns:
        raise ValueError(f"Missing required source columns: {missing_columns}")

    result = source[SOURCE_COLUMNS].copy()
    result["listing_id"] = result["listing_id"].astype("string")
    result["area"] = pd.to_numeric(result["area"], errors="coerce")
    result["bedrooms"] = pd.to_numeric(result["bedrooms"], errors="coerce")
    result["price_range"] = pd.to_numeric(result["price_range"], errors="coerce")

    result["latitude"], result["longitude"] = parse_coordinates(
        result.pop("latitude_longitude")
    )

    return result[OUTPUT_COLUMNS]


def main() -> None:
    source = pd.read_excel(INPUT_FILE, dtype={"listing_id": "string"})
    output = build_reliable_dataset(source)
    output.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")

    print(f"Input:  {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Rows: {len(output):,}; columns: {len(output.columns)}")
    print("Missing values after Step 1:")
    for column, count in output.isna().sum().items():
        if count:
            print(f"  - {column}: {count:,}")


if __name__ == "__main__":
    main()
