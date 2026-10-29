"""Create the Step 1 price-forecasting dataset from Data/v3/master_v3.csv.

This step keeps only the fields approved in the forecasting-data README. It
does not impute missing values or repair questionable observations; later
pipeline steps can make those decisions explicitly. The only rewriting is label
normalization of ``property_type`` and ``legal_status``, which v3 stores raw.
"""

from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_FILE = SCRIPT_DIR.parents[1] / "v3" / "master_v3.csv"
OUTPUT_FILE = SCRIPT_DIR / "reliable_features.xlsx"

SOURCE_COLUMNS = [
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

# v3 keeps the 7 raw crawl categories; forecasting (and the API) use two segments.
APARTMENT_TYPES = {"Căn hộ", "Căn hộ chung cư"}


def normalize_property_type(values: pd.Series) -> pd.Series:
    """Collapse raw property types into ``Căn hộ`` / ``Nhà đất``."""
    segment = values.map(lambda v: "Căn hộ" if v in APARTMENT_TYPES else "Nhà đất")
    return segment.where(values.notna())


def normalize_legal_status(values: pd.Series) -> pd.Series:
    """Map free-text legal status to a few classes (order matters)."""
    text = values.astype("string").str.lower().fillna("")
    result = pd.Series("Không rõ", index=values.index, dtype="string")
    # Later rules overwrite earlier ones, so the most specific class goes last.
    result[text.str.contains(r"sổ|hồng|đỏ|shr", regex=True)] = "Sổ hồng riêng"
    result[text.str.contains(r"hợp đồng|hđmb|hdmb", regex=True)] = "Hợp đồng mua bán"
    result[text.str.contains(r"chung|sdc", regex=True)] = "Sổ chung"
    result[text.str.contains(r"chờ|làm sổ|nộp hồ sơ", regex=True)] = "Đang chờ sổ"
    return result


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

    result["latitude"] = pd.to_numeric(result["latitude"], errors="coerce")
    result["longitude"] = pd.to_numeric(result["longitude"], errors="coerce")
    result["property_type"] = normalize_property_type(result["property_type"])
    result["legal_status"] = normalize_legal_status(result["legal_status"])

    return result[OUTPUT_COLUMNS]


def main() -> None:
    source = pd.read_csv(INPUT_FILE, dtype={"listing_id": "string"}, low_memory=False)
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
