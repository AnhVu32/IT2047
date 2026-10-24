"""Price prediction inference service.

Loads the trained machine learning model and computes real estate valuations
with confidence bounds based on property type segment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import numpy as np
import pandas as pd


class PricePredictionService:
    def __init__(self) -> None:
        self._bundle: Optional[Dict[str, Any]] = None

    def _resolve_model_path(self) -> Path:
        """Find the trained model bundle path in container or local environment."""
        local_artifact = Path(__file__).resolve().parent / "artifacts" / "best_model.joblib"
        if local_artifact.exists():
            return local_artifact

        # Fallback to repository root price-prediction/best_model.joblib
        repo_artifact = (
            Path(__file__).resolve().parents[4] / "price-prediction" / "best_model.joblib"
        )
        if repo_artifact.exists():
            return repo_artifact

        raise FileNotFoundError(
            f"Trained price model not found. Checked: {local_artifact} and {repo_artifact}"
        )

    def _get_bundle(self) -> Dict[str, Any]:
        """Lazy-load and cache the model bundle."""
        if self._bundle is None:
            model_path = self._resolve_model_path()
            self._bundle = joblib.load(model_path)
        return self._bundle

    def predict(
        self,
        property_type: str,
        area: float,
        bedrooms: int,
        latitude: float,
        longitude: float,
        district: str,
        legal_status: str = "Sổ hồng riêng",
    ) -> Dict[str, Any]:
        """Predict estimated price and confidence interval in billion VND."""
        bundle = self._get_bundle()
        model = bundle["model"]
        feature_names = bundle["feature_names"]

        # Build feature vector
        row = {col: 0 for col in feature_names}
        row["area"] = float(area)
        row["bedrooms"] = int(bedrooms)
        row["area_per_bedroom"] = round(float(area) / max(int(bedrooms), 1), 2)
        row["latitude"] = float(latitude)
        row["longitude"] = float(longitude)

        # One-hot encoded flags
        pt_col = f"property_type_{property_type}"
        if pt_col in row:
            row[pt_col] = 1

        ls_col = f"legal_status_{legal_status}"
        if ls_col in row:
            row[ls_col] = 1

        dist_col = f"district_{district}"
        if dist_col in row:
            row[dist_col] = 1

        # DataFrame with exact column order expected by scikit-learn
        input_df = pd.DataFrame([row])[feature_names]

        # Inference in log space, convert to billion VND
        pred_log = model.predict(input_df)[0]
        estimated_price = round(float(np.expm1(pred_log)), 2)

        # Segment-specific confidence interval margin
        # Empirical test results: Căn hộ MAPE ~14.9% (use +/-12%), Nhà đất MAPE ~21.0% (use +/-20%)
        is_apartment = "Căn hộ" in property_type
        margin_pct = 12.0 if is_apartment else 20.0

        lower_bound = round(estimated_price * (1.0 - margin_pct / 100.0), 2)
        upper_bound = round(estimated_price * (1.0 + margin_pct / 100.0), 2)

        return {
            "estimated_price": estimated_price,
            "lower_bound": max(lower_bound, 0.1),
            "upper_bound": upper_bound,
            "unit": "tỷ VND",
            "property_type": property_type,
            "district": district,
            "model_name": bundle.get("model_name", "HistGradientBoosting"),
        }


# Singleton service instance
price_prediction_service = PricePredictionService()
