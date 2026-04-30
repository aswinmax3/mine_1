import os
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_PATH = os.path.join(BASE_DIR, "datasets", "insurance.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models", "premium_prediction_model.pkl")


def train_premium_model():
    data = pd.read_csv(DATASET_PATH)

    required_columns = [
        "age",
        "sex",
        "bmi",
        "children",
        "smoker",
        "region",
        "charges",
    ]

    for column in required_columns:
        if column not in data.columns:
            raise ValueError(f"Missing column in dataset: {column}")

    X = data.drop("charges", axis=1)
    y = data["charges"]

    categorical_features = ["sex", "smoker", "region"]
    numeric_features = ["age", "bmi", "children"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical_features),
            ("numeric", "passthrough", numeric_features),
        ]
    )

    model = RandomForestRegressor(
        n_estimators=200,
        random_state=42,
        max_depth=12
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42
    )

    pipeline.fit(X_train, y_train)

    predictions = pipeline.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)

    print("Premium prediction model trained successfully.")
    print(f"MAE: {mae:.2f}")
    print(f"R2 Score: {r2:.2f}")
    print(f"Model saved at: {MODEL_PATH}")


if __name__ == "__main__":
    train_premium_model()