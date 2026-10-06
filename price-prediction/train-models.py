"""Train, benchmark, and save price prediction models.

Dataset source: Data/forecasting-data/step-4/encoded_data.xlsx

Steps:
1. Load clean encoded dataset.
2. Split into 80% train and 20% test sets (stratified by property type).
3. Train candidate models:
   - Ridge Regression (linear baseline)
   - Random Forest Regressor (bagging ensemble)
   - HistGradientBoosting Regressor (boosting ensemble)
4. Evaluate performance overall and separately by segment:
   - Overall (Combined)
   - Căn hộ (Apartments)
   - Nhà đất (Houses)
5. Save the best model artifact and multi-sheet evaluation report.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_FILE = SCRIPT_DIR.parent / "Data/forecasting-data/step-4/encoded_data.xlsx"
EVALUATION_FILE = SCRIPT_DIR / "model_evaluation.xlsx"
MODEL_FILE = SCRIPT_DIR / "best_model.joblib"


def load_and_split_data(file_path: Path):
    """Load data and split into train/test sets."""
    df = pd.read_excel(file_path)

    # Features X and target y
    X = df.drop(columns=["listing_id", "log_price"])
    y = df["log_price"]

    # Stratify by property type to keep balanced ratios
    stratify_col = (
        df["property_type_Nhà đất"] if "property_type_Nhà đất" in df.columns else None
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=stratify_col
    )
    return X_train, X_test, y_train, y_test, list(X.columns)


def compute_metrics(y_true_log: pd.Series, y_pred_log: np.ndarray) -> dict:
    """Compute regression metrics in log and real price space."""
    y_true_real = np.expm1(y_true_log)
    y_pred_real = np.expm1(y_pred_log)

    r2 = r2_score(y_true_log, y_pred_log)
    rmse_log = float(np.sqrt(mean_squared_error(y_true_log, y_pred_log)))
    mae_billion = float(mean_absolute_error(y_true_real, y_pred_real))
    median_ae_billion = float(np.median(np.abs(y_true_real - y_pred_real)))
    mape_pct = float(np.mean(np.abs((y_true_real - y_pred_real) / y_true_real)) * 100)

    return {
        "R2 Score": round(r2, 4),
        "RMSE (log)": round(rmse_log, 4),
        "MAE (billion VND)": round(mae_billion, 3),
        "Median AE (billion VND)": round(median_ae_billion, 3),
        "MAPE (%)": round(mape_pct, 2),
    }


def train_and_evaluate(X_train, X_test, y_train, y_test):
    """Train candidates and compute overall + segment benchmark metrics."""
    candidate_models = {
        "Ridge Regression": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "Random Forest": RandomForestRegressor(
            n_estimators=150, random_state=42, n_jobs=-1
        ),
        "HistGradientBoosting": HistGradientBoostingRegressor(
            max_iter=150, random_state=42
        ),
    }

    # Segment masks
    is_house = X_test["property_type_Nhà đất"] == 1
    is_apt = ~is_house
    segments = [
        ("Combined (All)", slice(None), len(y_test)),
        ("Căn hộ", is_apt, int(is_apt.sum())),
        ("Nhà đất", is_house, int(is_house.sum())),
    ]

    overall_results = []
    segment_results = []
    trained_models = {}

    for name, model in candidate_models.items():
        # Train model on all training data
        model.fit(X_train, y_train)
        trained_models[name] = model

        # Predict on entire test set
        y_pred_log = model.predict(X_test)

        # 1. Overall metrics
        overall_m = compute_metrics(y_test, y_pred_log)
        overall_results.append({"Model": name, **overall_m})

        # 2. Per-segment metrics
        for seg_name, mask, count in segments:
            seg_metrics = compute_metrics(y_test[mask], y_pred_log[mask])
            segment_results.append(
                {
                    "Model": name,
                    "Segment": seg_name,
                    "Sample Count": count,
                    **seg_metrics,
                }
            )

    overall_df = pd.DataFrame(overall_results)
    segment_df = pd.DataFrame(segment_results)
    return overall_df, segment_df, trained_models


def main() -> None:
    print(f"Loading dataset from: {INPUT_FILE}")
    X_train, X_test, y_train, y_test, feature_names = load_and_split_data(INPUT_FILE)

    print(f"Train records: {len(X_train):,}; Test records: {len(X_test):,}")
    print(f"Number of features: {len(feature_names)}")

    print("\nTraining and evaluating candidate models...")
    overall_df, segment_df, trained_models = train_and_evaluate(
        X_train, X_test, y_train, y_test
    )

    # Display overall benchmark
    print("\n=== OVERALL BENCHMARK RESULTS ===")
    print(overall_df.to_string(index=False))

    # Display segment breakdown
    print("\n=== SEGMENT BREAKDOWN (Căn hộ vs Nhà đất) ===")
    print(segment_df.to_string(index=False))

    # Save to Excel with two sheets
    with pd.ExcelWriter(EVALUATION_FILE, engine="openpyxl") as writer:
        overall_df.to_excel(writer, sheet_name="Overall", index=False)
        segment_df.to_excel(writer, sheet_name="By Segment", index=False)
    print(f"\nSaved multi-sheet evaluation results to: {EVALUATION_FILE}")

    # Determine best model by Overall R2 Score
    best_row = overall_df.sort_values(by="R2 Score", ascending=False).iloc[0]
    best_name = best_row["Model"]
    best_model = trained_models[best_name]

    # Best model segment metrics
    best_segment_metrics = segment_df[segment_df["Model"] == best_name].to_dict(
        orient="records"
    )

    # Save best model along with metadata
    model_bundle = {
        "model_name": best_name,
        "model": best_model,
        "feature_names": feature_names,
        "metrics_overall": best_row.to_dict(),
        "metrics_by_segment": best_segment_metrics,
    }
    joblib.dump(model_bundle, MODEL_FILE)
    print(f"Saved best model ({best_name}) to: {MODEL_FILE}")


if __name__ == "__main__":
    main()
