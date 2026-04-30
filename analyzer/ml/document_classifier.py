def classify_document(text):
    text = text.lower()

    if any(word in text for word in ['policy number', 'premium', 'coverage', 'sum insured']):
        return 'policy'

    elif any(word in text for word in ['claim form', 'claim settlement', 'claim amount']):
        return 'claim'

    elif any(word in text for word in ['diagnosis', 'hospital', 'medical report', 'patient']):
        return 'medical'

    elif any(word in text for word in ['proposal form', 'applicant', 'nominee']):
        return 'proposal'

    elif any(word in text for word in ['legal', 'court', 'agreement', 'terms and conditions']):
        return 'legal'

    else:
        return 'unknown'