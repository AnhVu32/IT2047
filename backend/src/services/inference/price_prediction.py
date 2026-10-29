"""Price prediction inference service.

Loads the trained machine learning model and computes real estate valuations
with confidence bounds based on property type segment.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import numpy as np
import pandas as pd


# shortcut: label rules duplicated from Data/forecasting-data/step-1/remove-unreliable-features.py
# (DB stores the raw v3 labels, the model was trained on the normalized ones); keep in sync on retrain.
_APARTMENT_TYPES = {"Căn hộ", "Căn hộ chung cư"}
_COORDINATES = re.compile(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)")
# Training domain: step-2 coordinate box and step-3 outlier rules.
_LAT_RANGE, _LON_RANGE = (10.3, 11.6), (106.3, 107.6)
# Per type: (min area, max area, max bedrooms, min price tỷ, max price tỷ, min tr/m2, max tr/m2).
_DOMAIN = {"Căn hộ": (25, 150, 4, 1.0, 20.0, 20, 180), "Nhà đất": (20, 350, 8, 1.5, 40.0, 30, 350)}


def normalize_legal_status(value: Optional[str]) -> str:
    text = (value or "").lower()
    if re.search(r"chờ|làm sổ|nộp hồ sơ", text):
        return "Đang chờ sổ"
    if re.search(r"chung|sdc", text):
        return "Sổ chung"
    if re.search(r"hợp đồng|hđmb|hdmb", text):
        return "Hợp đồng mua bán"
    if re.search(r"sổ|hồng|đỏ|shr", text):
        return "Sổ hồng riêng"
    return "Không rõ"


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

    def estimate_listing(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Compare a stored listing's asking price with the model estimate.

        Raises ValueError (user-facing, Vietnamese) when the listing cannot be scored reliably.
        """
        coords = _COORDINATES.search(item.get("latitude_longitude") or "")
        area, bedrooms, asking = item.get("area"), item.get("bedrooms"), item.get("price_range")
        if not (coords and area and bedrooms and asking):
            raise ValueError("Tin đăng thiếu diện tích, số phòng ngủ, giá hoặc toạ độ để định giá.")

        latitude, longitude = float(coords.group(1)), float(coords.group(2))
        property_type = "Căn hộ" if item.get("property_type") in _APARTMENT_TYPES else "Nhà đất"
        min_area, max_area, max_bedrooms, min_price, max_price, min_m2, max_m2 = _DOMAIN[property_type]
        per_m2 = float(asking) * 1000 / float(area)
        district = item.get("district")
        # First failing check wins; the message is shown to users, so say which limit was hit.
        checks = [
            (_LAT_RANGE[0] <= latitude <= _LAT_RANGE[1] and _LON_RANGE[0] <= longitude <= _LON_RANGE[1],
             "Toạ độ của tin nằm ngoài khu vực TP.HCM."),
            (f"district_{district}" in self._get_bundle()["feature_names"],
             "Khu vực (phường/xã) của tin chưa có trong dữ liệu huấn luyện."),
            (min_area <= float(area) <= max_area,
             f"Diện tích {float(area):g} m² nằm ngoài khoảng {min_area}–{max_area} m² mô hình được huấn luyện."),
            (1 <= int(bedrooms) <= max_bedrooms,
             f"Số phòng ngủ ({int(bedrooms)}) nằm ngoài khoảng 1–{max_bedrooms} mô hình được huấn luyện."),
            # Asking price outside the trained price band: the comparison would be meaningless.
            (min_price <= float(asking) <= max_price,
             f"Giá rao nằm ngoài khoảng {min_price:g}–{max_price:g} tỷ mô hình được huấn luyện."),
            (min_m2 <= per_m2 <= max_m2,
             f"Đơn giá {per_m2:.0f} triệu/m² nằm ngoài khoảng {min_m2}–{max_m2} triệu/m² mô hình được huấn luyện."),
        ]
        for ok, reason in checks:
            if not ok:
                raise ValueError(reason)

        result = self.predict(
            property_type=property_type,
            area=float(area),
            bedrooms=int(bedrooms),
            latitude=latitude,
            longitude=longitude,
            district=district,
            legal_status=normalize_legal_status(item.get("legal_status")),
        )
        asking = float(asking)
        result["asking_price"] = asking
        result["diff_pct"] = round((asking / result["estimated_price"] - 1.0) * 100.0, 1)
        result["verdict"] = (
            "below" if asking < result["lower_bound"] else "above" if asking > result["upper_bound"] else "within"
        )
        return result


# Singleton service instance
price_prediction_service = PricePredictionService()
