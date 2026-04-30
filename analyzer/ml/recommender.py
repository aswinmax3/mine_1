def generate_recommendation(
    document_type,
    premium,
    coverage,
    exclusions,
    claim_terms,
    predicted_cost=None,
    ml_risk_level=None
):
    recommendation = []

    risk_level = ml_risk_level or "Low"

    if document_type == "policy":
        recommendation.append("This document appears to be an insurance policy.")

        if premium == "Not found":
            recommendation.append("Premium amount is missing, so the user should verify pricing manually.")
            risk_level = "Medium"

        if coverage == "Not found":
            recommendation.append("Coverage amount is missing, which creates transparency risk.")
            risk_level = "High"

        if predicted_cost:
            recommendation.append(
                f"The ML model estimates the expected insurance cost as approximately ₹{predicted_cost}."
            )

        if exclusions and exclusions != "No major exclusions found.":
            recommendation.append(
                "Important exclusions were detected. The user should review conditions that are not covered."
            )
            if risk_level == "Low":
                risk_level = "Medium"

        if claim_terms and claim_terms != "No claim terms found.":
            recommendation.append(
                "Claim-related terms are available, but the user should verify required documents and settlement conditions."
            )

        if risk_level == "High":
            recommendation.append(
                "Recommendation: This policy needs careful review before purchase or approval."
            )
        elif risk_level == "Medium":
            recommendation.append(
                "Recommendation: This policy may be acceptable, but premium, coverage, and exclusions should be compared."
            )
        else:
            recommendation.append(
                "Recommendation: This policy appears comparatively safer based on extracted and predicted values."
            )

    elif document_type == "claim":
        recommendation.append("This appears to be a claim-related document.")
        recommendation.append("Verify claim amount, hospital records, bills, and settlement terms.")
        risk_level = "Medium"

    elif document_type == "medical":
        recommendation.append("This appears to be a medical document.")
        recommendation.append("Medical history, diagnosis, and treatment cost should be verified before claim approval.")
        risk_level = "Medium"

    elif document_type == "proposal":
        recommendation.append("This appears to be a proposal form.")
        recommendation.append("Applicant details, nominee information, and declared health conditions should be verified.")

    elif document_type == "legal":
        recommendation.append("This appears to be a legal insurance document.")
        recommendation.append("Legal clauses should be reviewed carefully before acceptance.")
        risk_level = "High"

    else:
        recommendation.append("Document type could not be clearly identified.")
        recommendation.append("Manual verification is recommended.")
        risk_level = "High"

    return {
        "recommendation": " ".join(recommendation),
        "risk_level": risk_level
    }