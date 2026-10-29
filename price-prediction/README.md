# Real Estate Price Prediction Module

This module trains, evaluates, and serves the price prediction model using the processed and encoded dataset from `Data/forecasting-data/step-4/encoded_data.xlsx` (built from `Data/v3/master_v3.csv`, 6,703 listings → 5,009 after cleaning).

## 1. Structure

- `train-models.py`:
  - Splits data into 80% train (4,007 records) and 20% test (1,002 records), stratified by property type.
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

### Overall Benchmark (N = 1,002 test samples, data v3)

| Model | R2 Score | RMSE (log) | MAE (billion VND) | Median AE (billion VND) | MAPE (%) |
|---|---|---|---|---|---|
| **HistGradientBoosting** | **0.8330** | **0.2174** | 1.560 | 0.820 | 19.21% |
| Random Forest | 0.8321 | 0.2180 | **1.508** | **0.712** | **18.23%** |
| Ridge Regression | 0.7480 | 0.2671 | 2.111 | 1.116 | 25.10% |

### Segment Breakdown for Best Model (HistGradientBoosting)

| Segment | Sample Count | R2 Score | RMSE (log) | MAE (billion VND) | Median AE (billion VND) | MAPE (%) |
|---|---|---|---|---|---|---|
| **Căn hộ** *(Apartments)* | 279 | **0.9005** | **0.1362** | **0.599** | **0.375** | **13.56%** |
| **Nhà đất** *(Houses)* | 723 | **0.7398** | **0.2416** | **1.931** | **1.127** | **21.39%** |
| **Combined** | 1,002 | **0.8330** | **0.2174** | **1.560** | **0.820** | **19.21%** |

*Not directly comparable with the previous run (3,037-listing `Final_Data`, 463 test samples, R2 0.7971): different data and a different random test split.*

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
