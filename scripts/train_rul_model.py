#!/usr/bin/env python3
"""Train XGBoost RUL model and register in Snowflake Model Registry.
Usage: SNOWFLAKE_CONNECTION_NAME=demo43 python train_rul_model.py
"""
import os
import snowflake.connector
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

conn = snowflake.connector.connect(
    connection_name=os.getenv("SNOWFLAKE_CONNECTION_NAME") or "demo43"
)
cur = conn.cursor()

print("Loading training data...")
cur.execute("SELECT * FROM MANUFACTURING_MAINTENANCE.ML.RUL_TRAINING_DATA")
cols = [d[0] for d in cur.description]
df = pd.DataFrame(cur.fetchall(), columns=cols)
print(f"  {len(df)} rows, {len(df.columns)} columns")

feature_cols = ["VIBRATION", "TEMPERATURE", "PRESSURE", "CURRENT_A", "RPM",
                "EQUIPMENT_AGE_DAYS", "DAYS_SINCE_MAINTENANCE", "FAILURE_COUNT",
                "AVG_DOWNTIME", "AVG_FAILURE_COST", "DAYS_SINCE_LAST_FAILURE"]
target_col = "DAYS_TO_FAILURE"

X = df[feature_cols].astype(float)
y = df[target_col].astype(float)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print(f"  Train: {len(X_train)}, Test: {len(X_test)}")

print("Training XGBoost model...")
model = xgb.XGBRegressor(
    n_estimators=200, max_depth=5, learning_rate=0.1,
    reg_lambda=1.0, objective="reg:squarederror", random_state=42
)
model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
rmse = mean_squared_error(y_test, y_pred, squared=False)
r2 = r2_score(y_test, y_pred)
print(f"  MAE: {mae:.1f} days, RMSE: {rmse:.1f} days, R2: {r2:.3f}")

print("Registering model in Snowflake Model Registry...")
try:
    from snowflake.snowpark import Session
    from snowflake.ml.registry import Registry
    from snowflake.ml.model import task

    session = Session.builder.configs({"connection": conn}).create()
    reg = Registry(session=session, database_name="MANUFACTURING_MAINTENANCE", schema_name="ML")

    mv = reg.log_model(
        model,
        model_name="RUL_PREDICTOR",
        version_name="v1",
        conda_dependencies=["xgboost", "scikit-learn"],
        comment="XGBoost Remaining Useful Life predictor — trained on 200K sensor readings + 500 failure events",
        metrics={"mae_days": round(mae, 1), "rmse_days": round(rmse, 1), "r2": round(r2, 3)},
        sample_input_data=X_test.head(10),
        task=task.Task.TABULAR_REGRESSION,
    )
    print(f"  Model registered: MANUFACTURING_MAINTENANCE.ML.RUL_PREDICTOR v1")
    print(f"  Metrics: MAE={mae:.1f}d, RMSE={rmse:.1f}d, R2={r2:.3f}")
except ImportError:
    print("  snowflake-ml-python not available — skipping registry. Model trained successfully.")
    print(f"  Metrics: MAE={mae:.1f}d, RMSE={rmse:.1f}d, R2={r2:.3f}")
except Exception as e:
    print(f"  Registry error: {e}")
    print(f"  Model trained successfully. Metrics: MAE={mae:.1f}d, RMSE={rmse:.1f}d, R2={r2:.3f}")

conn.close()
print("Done.")
