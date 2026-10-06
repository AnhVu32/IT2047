# Real Estate Price Prediction Module

This module trains, evaluates, and serves the price prediction model using the processed and encoded dataset from `Data/forecasting-data/step-4/encoded_data.xlsx`.

## 1. Structure

- `train-models.py`:
  - Splits data into 80% train (1,849 records) and 20% test (463 records), stratified by property type.
  - Benchmarks 3 models: Ridge Regression, Random Forest, and HistGradientBoosting.
  - Evaluates models overall and by segment (`Căn hộ` vs `Nhà đất`).
  - Exports a multi-sheet benchmark report to `model_evaluation.xlsx` (Sheets: `Overall` and `By Segment`).
  - Saves the best model artifact to `best_model.joblib`.

- `predict.py`:
  - Provides a single property inference function `predict_price(...)`.
  - Takes property attributes (`property_type`, `area`, `bedrooms`, `latitude`, `longitude`, `district`, `legal_status`).
  - Returns estimated price in billion VND.

- `model_evaluation.xlsx`: Multi-sheet benchmark metrics.
- `best_model.joblib`: Model artifact containing trained model, feature metadata, and metrics.

## 2. Benchmark Results

### Overall Benchmark (N = 463 test samples)

| Model | R2 Score | RMSE (log) | MAE (billion VND) | Median AE (billion VND) | MAPE (%) |
|---|---|---|---|---|---|
| **HistGradientBoosting** | **0.7971** | **0.2350** | **1.773** | **0.931** | **19.91%** |
| Random Forest | 0.7923 | 0.2378 | 1.736 | 0.856 | 19.98% |
| Ridge Regression | 0.6942 | 0.2886 | 2.346 | 1.271 | 26.31% |

### Segment Breakdown for Best Model (HistGradientBoosting)

| Segment | Sample Count | R2 Score | RMSE (log) | MAE (billion VND) | Median AE (billion VND) | MAPE (%) |
|---|---|---|---|---|---|---|
| **Căn hộ** *(Apartments)* | 83 | **0.8507** | **0.1622** | **0.665** | **0.358** | **14.89%** |
| **Nhà đất** *(Houses)* | 380 | **0.7321** | **0.2481** | **2.015** | **1.113** | **21.01%** |
| **Combined** | 463 | **0.7971** | **0.2350** | **1.773** | **0.931** | **19.91%** |

## 3. How to Run Locally

### Train & Benchmark
```bash
python train-models.py
```

### Run Prediction Example
```bash
python predict.py
```

## 4. Backend API Integration (Hybrid Setup)

The trained model is deployed to the FastAPI backend via the hybrid setup:

- **Model Artifact**: Copied to `backend/src/services/inference/artifacts/best_model.joblib`.
- **Inference Service**: Implemented in `backend/src/services/inference/price_prediction.py`.
- **API Endpoint**: `POST /v1/properties/predict-price`.

### Request Example
```http
POST /v1/properties/predict-price
Content-Type: application/json

{
  "property_type": "Nhà đất",
  "area": 80.0,
  "bedrooms": 3,
  "latitude": 10.745,
  "longitude": 106.705,
  "district": "Phường Tân Hưng",
  "legal_status": "Sổ hồng riêng"
}
```

### Response Example
```json
{
  "data": {
    "estimated_price": 9.01,
    "lower_bound": 7.21,
    "upper_bound": 10.81,
    "unit": "tỷ VND",
    "property_type": "Nhà đất",
    "district": "Phường Tân Hưng",
    "model_name": "HistGradientBoosting"
  },
  "errors": [],
  "status": "success"
}
```

*Note: `lower_bound` and `upper_bound` are automatically calibrated based on property segment (±12% for Căn hộ, ±20% for Nhà đất).*
