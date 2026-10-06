"""Train, benchmark, and save price prediction models.

Steps:
1. Load clean encoded dataset from step-4/encoded_data.xlsx.
2. Split into 80% train and 20% test sets (stratified by property type).
3. Train 3 candidate models:
   - Ridge Regression (linear baseline)
   - Random Forest Regressor (bagging ensemble)
   - HistGradientBoosting Regressor (boosting ensemble)
4. Evaluate performance in both log space (R2, RMSE) and real price space (MAE, Median AE, MAPE).
5. Save the best model artifact and evaluation report.
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
INPUT_FILE = SCRIPT_DIR.parent / "step-4/encoded_data.xlsx"
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


def train_and_evaluate(X_train, X_test, y_train, y_test):
    """Train candidates and compute benchmark metrics."""
    candidate_models = {
        "Ridge Regression": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "Random Forest": RandomForestRegressor(
            n_estimators=150, random_state=42, n_jobs=-1
        ),
        "HistGradientBoosting": HistGradientBoostingRegressor(
            max_iter=150, random_state=42
        ),
    }

    results = []
    trained_models = {}

    y_test_real = np.expm1(y_test)

    for name, model in candidate_models.items():
        # Train model
        model.fit(X_train, y_train)
        trained_models[name] = model

        # Predict
        y_pred_log = model.predict(X_test)
        y_pred_real = np.expm1(y_pred_log)

        # Metrics
        r2 = r2_score(y_test, y_pred_log)
        rmse_log = float(np.sqrt(mean_squared_error(y_test, y_pred_log)))
        mae_billion = float(mean_absolute_error(y_test_real, y_pred_real))
        median_ae_billion = float(np.median(np.abs(y_test_real - y_pred_real)))
        mape_pct = float(np.mean(np.abs((y_test_real - y_pred_real) / y_test_real)) * 100)

        results.append(
            {
                "Model": name,
                "R2 Score": round(r2, 4),
                "RMSE (log)": round(rmse_log, 4),
                "MAE (billion VND)": round(mae_billion, 3),
                "Median AE (billion VND)": round(median_ae_billion, 3),
                "MAPE (%)": round(mape_pct, 2),
            }
        )

    return pd.DataFrame(results), trained_models


def main() -> None:
    print(f"Loading dataset from: {INPUT_FILE}")
    X_train, X_test, y_train, y_test, feature_names = load_and_split_data(INPUT_FILE)

    print(f"Train records: {len(X_train):,}; Test records: {len(X_test):,}")
    print(f"Number of features: {len(feature_names)}")

    print("\nTraining and evaluating candidate models...")
    eval_df, trained_models = train_and_evaluate(X_train, X_test, y_train, y_test)

    # Display evaluation table
    print("\n=== MODEL BENCHMARK RESULTS ===")
    print(eval_df.to_string(index=False))

    # Save evaluation table
    eval_df.to_excel(EVALUATION_FILE, index=False, engine="openpyxl")
    print(f"\nSaved evaluation results to: {EVALUATION_FILE}")

    # Determine best model by R2 Score
    best_row = eval_df.sort_values(by="R2 Score", ascending=False).iloc[0]
    best_name = best_row["Model"]
    best_model = trained_models[best_name]

    # Save best model along with metadata
    model_bundle = {
        "model_name": best_name,
        "model": best_model,
        "feature_names": feature_names,
        "metrics": best_row.to_dict(),
    }
    joblib.dump(model_bundle, MODEL_FILE)
    print(f"Saved best model ({best_name}) to: {MODEL_FILE}")


if __name__ == "__main__":
    main()
