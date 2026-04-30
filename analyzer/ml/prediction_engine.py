import os
import joblib
import pandas as pd


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PREMIUM_MODEL_PATH = os.path.join(BASE_DIR, "models", "premium_prediction_model.pkl")


def predict_expected_cost(age, sex, bmi, children, smoker, region):
    if not os.path.exists(PREMIUM_MODEL_PATH):
        return {
            "success": False,
            "predicted_cost": None,
            "message": "Premium prediction model not trained yet."
        }

    model = joblib.load(PREMIUM_MODEL_PATH)

    input_data = pd.DataFrame([{
        "age": age,
        "sex": sex,
        "bmi": bmi,
        "children": children,
        "smoker": smoker,
        "region": region,
    }])

    predicted_cost = model.predict(input_data)[0]

    return {
        "success": True,
        "predicted_cost": round(float(predicted_cost), 2),
        "message": "Prediction successful."
    }


def calculate_real_life_risk(predicted_cost, coverage_amount, premium_amount):
    if predicted_cost is None:
        return "Unknown"

    try:
        coverage_amount = float(str(coverage_amount).replace(",", "").replace("₹", ""))
        premium_amount = float(str(premium_amount).replace(",", "").replace("₹", ""))
    except:
        return "Medium"

    if coverage_amount < predicted_cost:
        return "High"

    if premium_amount > predicted_cost * 0.45:
        return "Medium"

    return "Low"