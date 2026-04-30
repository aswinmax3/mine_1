import re
import spacy

nlp = spacy.load("en_core_web_sm")


def extract_policy_number(text):
    patterns = [
        r'Policy\s*Number[:\s]*([A-Z0-9-]+)',
        r'Policy\s*No[:\s]*([A-Z0-9-]+)',
        r'Policy\s*ID[:\s]*([A-Z0-9-]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return "Not found"


def extract_premium_amount(text):
    pattern = r'(Premium|Annual Premium|Monthly Premium)[:\s₹$]*([0-9,]+)'
    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        return match.group(2)

    return "Not found"


def extract_coverage_amount(text):
    pattern = r'(Coverage|Sum Insured|Insurance Cover)[:\s₹$]*([0-9,]+)'
    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        return match.group(2)

    return "Not found"


def extract_exclusions(text):
    keywords = ['exclusion', 'not covered', 'excluded', 'limitations']
    sentences = split_sentences(text)

    results = []
    for sentence in sentences:
        if any(keyword in sentence.lower() for keyword in keywords):
            results.append(sentence)

    return " ".join(results[:5]) if results else "No major exclusions found."


def extract_claim_terms(text):
    keywords = ['claim', 'settlement', 'documents required', 'claim process']
    sentences = split_sentences(text)

    results = []
    for sentence in sentences:
        if any(keyword in sentence.lower() for keyword in keywords):
            results.append(sentence)

    return " ".join(results[:5]) if results else "No claim terms found."


def split_sentences(text):
    doc = nlp(text)
    return [sent.text.strip() for sent in doc.sents]


def extract_all_details(text):
    return {
        "policy_number": extract_policy_number(text),
        "premium_amount": extract_premium_amount(text),
        "coverage_amount": extract_coverage_amount(text),
        "exclusions": extract_exclusions(text),
        "claim_terms": extract_claim_terms(text),
    }