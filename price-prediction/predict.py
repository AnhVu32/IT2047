"""Single property price prediction utility using the trained best model."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_FILE = SCRIPT_DIR / "best_model.joblib"


def predict_price(
    property_type: str,
    area: float,
    bedrooms: int,
    latitude: float,
    longitude: float,
    district: str,
    legal_status: str = "Sổ hồng riêng",
) -> float:
    """Predict estimated property price in billion VND."""
    bundle = joblib.load(MODEL_FILE)
    model = bundle["model"]
    feature_names = bundle["feature_names"]

    # Initialize zero vector for all trained features
    row = {col: 0 for col in feature_names}

    # Populate numerical features
    row["area"] = float(area)
    row["bedrooms"] = int(bedrooms)
    row["area_per_bedroom"] = round(float(area) / int(bedrooms), 2)
    row["latitude"] = float(latitude)
    row["longitude"] = float(longitude)

    # Populate one-hot categoricals
    pt_col = f"property_type_{property_type}"
    if pt_col in row:
        row[pt_col] = 1

    ls_col = f"legal_status_{legal_status}"
    if ls_col in row:
        row[ls_col] = 1

    dist_col = f"district_{district}"
    if dist_col in row:
        row[dist_col] = 1

    # Form single-row DataFrame with exact feature order
    input_df = pd.DataFrame([row])[feature_names]

    # Predict log-price and convert back to billion VND
    pred_log = model.predict(input_df)[0]
    pred_billion = float(np.expm1(pred_log))

    return round(pred_billion, 2)


def main() -> None:
    # Example prediction: House in District 7 (Tan Hung)
    sample_house = {
        "property_type": "Nhà đất",
        "area": 80.0,
        "bedrooms": 3,
        "latitude": 10.745,
        "longitude": 106.705,
        "district": "Phường Tân Hưng",
        "legal_status": "Sổ hồng riêng",
    }

    predicted_price = predict_price(**sample_house)

    print("=== EXAMPLE PREDICTION ===")
    for key, value in sample_house.items():
        print(f"  {key}: {value}")
    print(f"\nEstimated Price: {predicted_price} billion VND")


if __name__ == "__main__":
    main()
