import os
import json
import time
import re
from difflib import SequenceMatcher

import httpx
from django.conf import settings

AI_LAST_ERROR = None
AI_LAST_ERRORS = []


# --------------------
# Gemini / Groq / OpenRouter clients (lazy imports)
# --------------------

def _init_clients():
    gemini_model = (getattr(settings, "GEMINI_MODEL", None) or "gemini-2.0-flash").strip()
    groq_model = (getattr(settings, "GROQ_MODEL", None) or "llama-3.3-70b-versatile").strip()
    openrouter_model = (getattr(settings, "OPENROUTER_MODEL", None) or "openrouter/free").strip()
    provider_order = getattr(settings, "AI_PROVIDER_ORDER", None) or ["gemini", "groq", "openrouter"]
    gemini_key = (getattr(settings, "GEMINI_API_KEY", None) or "").strip()
    groq_key = (getattr(settings, "GROQ_API_KEY", None) or "").strip()
    openrouter_key = (getattr(settings, "OPENROUTER_API_KEY", None) or "").strip()

    gemini_client = None
    gemini_model_name = gemini_model
    if gemini_key:
        try:
            from google import genai as google_genai
            gemini_client = ("google-genai", google_genai.Client(api_key=gemini_key))
        except Exception:
            try:
                import google.generativeai as google_genai_legacy
                google_genai_legacy.configure(api_key=gemini_key)
                gemini_client = ("google-generativeai", google_genai_legacy.GenerativeModel(gemini_model))
            except Exception:
                gemini_client = None

    groq_client = None
    if groq_key:
        try:
            from groq import Groq
            groq_client = Groq(api_key=groq_key)
        except Exception:
            groq_client = None

    return gemini_client, gemini_model_name, groq_client, openrouter_key, groq_model, openrouter_model, provider_order


(
    _GEMINI_CLIENT,
    _GEMINI_MODEL,
    _GROQ_CLIENT,
    _OPENROUTER_KEY,
    _GROQ_MODEL,
    _OPENROUTER_MODEL,
    _AI_PROVIDER_ORDER,
) = _init_clients()

def _safe_json_loads(text: str):
    # Remove code fences if any
    text = _clean_ai_response(text)
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    # If model returns extra text, try to extract first JSON object/array
    if not text.startswith("{") and not text.startswith("["):
        m = re.search(r"({[\s\S]*}|\[[\s\S]*\])", text)
        if m:
            text = m.group(1)

    return json.loads(text)


def _clean_ai_response(text: str) -> str:
    text = str(text or "").strip()
    text = re.sub(r"</?(?:assistant|user|system)>", "", text, flags=re.IGNORECASE)
    text = text.replace("<|assistant|>", "").replace("<|user|>", "").replace("<|system|>", "")
    return text.strip()


def _call_gemini(prompt: str) -> str:
    if _GEMINI_CLIENT is None:
        raise RuntimeError("GEMINI_API_KEY not configured")
    sdk_name, client = _GEMINI_CLIENT
    if sdk_name == "google-genai":
        r = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=prompt,
        )
    else:
        r = client.generate_content(prompt)
    return getattr(r, "text", None) or str(r)


def _call_groq(prompt: str) -> str:
    if _GROQ_CLIENT is None:
        raise RuntimeError("GROQ_API_KEY not configured")

    r = _GROQ_CLIENT.chat.completions.create(
        model=_GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1200,
    )
    return r.choices[0].message.content


def _call_openrouter(prompt: str) -> str:
    if not _OPENROUTER_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not configured")

    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {_OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Insurance AI Policy Analyzer",
        },
        json={
            "model": _OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1200,
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]


def ask_ai(prompt: str, json_mode: bool = False):
    """Fallback chain: Gemini -> Groq -> OpenRouter"""

    global AI_LAST_ERROR, AI_LAST_ERRORS
    AI_LAST_ERROR = None
    AI_LAST_ERRORS = []
    provider_map = {
        "gemini": _call_gemini,
        "groq": _call_groq,
        "openrouter": _call_openrouter,
    }
    fns = [provider_map[name] for name in _AI_PROVIDER_ORDER if name in provider_map]
    if not fns:
        fns = [_call_gemini, _call_groq, _call_openrouter]
    last_err = None

    for fn in fns:
        try:
            result = fn(prompt)
            if json_mode:
                return _safe_json_loads(result)
            return _clean_ai_response(result)
        except Exception as e:
            last_err = e
            AI_LAST_ERRORS.append(f"{fn.__name__}: {e.__class__.__name__}: {e}")
            # small backoff to avoid hammering
            time.sleep(0.6)

    if last_err:
        AI_LAST_ERROR = f"{last_err.__class__.__name__}: {last_err}"
        print("AI provider errors: " + " | ".join(AI_LAST_ERRORS))
        return None
    return None


def get_ai_status():
    return {
        "provider_order": list(_AI_PROVIDER_ORDER),
        "gemini_configured": _GEMINI_CLIENT is not None,
        "gemini_model": _GEMINI_MODEL,
        "groq_configured": _GROQ_CLIENT is not None,
        "groq_model": _GROQ_MODEL,
        "openrouter_configured": bool(_OPENROUTER_KEY),
        "openrouter_model": _OPENROUTER_MODEL,
        "last_errors": list(AI_LAST_ERRORS),
    }


# --------------------
# Retrieval / comparison helpers
# --------------------

KEY_ASPECTS = [
    "sum insured",
    "coverage",
    "premium",
    "waiting period",
    "pre existing disease",
    "room rent",
    "co pay",
    "deductible",
    "maternity",
    "day care",
    "cashless",
    "claim",
    "exclusion",
    "renewal",
]


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "")
    return text.strip()


def _chunk_text(text: str, chunk_size: int = 850, overlap: int = 170):
    words = _clean_text(text).split()
    if not words:
        return []

    chunks = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks


def _best_chunks(text: str, query: str, limit: int = 5):
    chunks = _chunk_text(text)
    if not chunks:
        return ""

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        corpus = chunks + [query]
        vectors = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform(corpus)
        scores = cosine_similarity(vectors[-1], vectors[:-1]).flatten()
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        selected = [chunks[i] for i, score in ranked[:limit] if score > 0]
        if selected:
            return "\n\n---\n\n".join(selected)
    except Exception:
        pass

    query_terms = {term.lower() for term in re.findall(r"[a-zA-Z0-9]+", query) if len(term) > 2}
    ranked = []
    for index, chunk in enumerate(chunks):
        terms = set(re.findall(r"[a-zA-Z0-9]+", chunk.lower()))
        ranked.append((len(query_terms & terms), index, chunk))
    ranked.sort(reverse=True)
    selected = [chunk for score, _, chunk in ranked[:limit] if score > 0]
    return "\n\n---\n\n".join(selected or chunks[:limit])


def _extract_amounts(text: str):
    patterns = [
        r"(?:rs\.?|inr|₹)\s*[\d,]+(?:\.\d+)?\s*(?:lakh|lac|crore|cr)?",
        r"\b\d+(?:\.\d+)?\s*(?:lakh|lac|crore|cr)\b",
        r"\b\d{1,3}(?:,\d{2,3})+(?:\.\d+)?\b",
    ]
    found = []
    for pattern in patterns:
        found.extend(re.findall(pattern, text or "", flags=re.IGNORECASE))
    return list(dict.fromkeys(item.strip() for item in found))[:8]


def _extract_waiting_periods(text: str):
    pattern = r"\b(?:waiting period|wait period|pre[- ]existing|specific disease|maternity)[^.]{0,120}?(?:\d+\s*(?:days?|months?|years?))"
    return list(dict.fromkeys(re.findall(pattern, text or "", flags=re.IGNORECASE)))[:8]


def _extract_percentages(text: str):
    return list(dict.fromkeys(re.findall(r"\b\d+(?:\.\d+)?\s*%", text or "")))[:8]


def _amount_to_number(value: str):
    value = (value or "").lower().replace(",", "")
    number_match = re.search(r"\d+(?:\.\d+)?", value)
    if not number_match:
        return None

    amount = float(number_match.group(0))
    if "crore" in value or " cr" in value:
        amount *= 10000000
    elif "lakh" in value or "lac" in value:
        amount *= 100000
    return amount


def _extract_policy_facts(text: str):
    text = _clean_text(text)
    lowered = text.lower()
    return {
        "amounts": _extract_amounts(text),
        "waiting_periods": _extract_waiting_periods(text),
        "percentages": _extract_percentages(text),
        "mentions": {
            aspect: (aspect in lowered)
            for aspect in KEY_ASPECTS
        },
    }


def _fallback_multi_answer(policy_evidence, question: str):
    lowered_question = (question or "").lower()
    lines = ["AI is temporarily unavailable or quota-limited, so I checked the extracted policy text directly."]
    best_amount = None
    best_amount_policy = None

    for item in policy_evidence:
        facts = item["facts"]
        amounts = facts.get("amounts") or []
        waiting = facts.get("waiting_periods") or []
        percentages = facts.get("percentages") or []
        mentions = facts.get("mentions") or {}

        for amount_text in amounts:
            numeric_amount = _amount_to_number(amount_text)
            if numeric_amount is not None and (best_amount is None or numeric_amount > best_amount):
                best_amount = numeric_amount
                best_amount_policy = item["name"]

        details = []
        if amounts:
            details.append("amounts: " + ", ".join(amounts[:3]))
        if waiting:
            details.append("waiting periods: " + "; ".join(waiting[:2]))
        if percentages:
            details.append("percentages/sub-limits: " + ", ".join(percentages[:3]))
        if mentions.get("room rent"):
            details.append("room rent is mentioned")
        if mentions.get("co pay") or mentions.get("deductible"):
            details.append("co-pay/deductible is mentioned")
        if mentions.get("claim") or mentions.get("cashless"):
            details.append("claim/cashless is mentioned")

        summary = "; ".join(details) or item["preview"]
        lines.append(f"- {item['name']}: {summary}")

    if best_amount_policy and any(term in lowered_question for term in ["higher", "highest", "more", "sum insured", "coverage"]):
        lines.append(f"\nLikely answer: {best_amount_policy} has the highest detected coverage amount in the extracted text.")

    if any(term in lowered_question for term in ["room rent", "restriction", "sub-limit", "sublimit"]):
        unrestricted = [
            item["name"]
            for item in policy_evidence
            if "no room rent" in item["preview"].lower() or "without room rent" in item["preview"].lower()
        ]
        if unrestricted:
            lines.append(f"\nRoom-rent note: {', '.join(unrestricted)} appears to have no room-rent restriction in the extracted text.")

    return "\n".join(lines)


def _policy_context(text: str, extra_query: str = "", limit: int = 7):
    query = " ".join(KEY_ASPECTS + [extra_query])
    chunks = _best_chunks(text, query, limit=limit)
    return chunks or _clean_text(text)[:9000]


def _value_score(facts: dict):
    mentions = facts.get("mentions", {})
    score = 0
    score += 8 if facts.get("amounts") else 0
    score += 8 if facts.get("waiting_periods") else 0
    score += 5 if facts.get("percentages") else 0
    score += sum(2 for value in mentions.values() if value)
    if mentions.get("exclusion"):
        score -= 3
    if mentions.get("co pay") or mentions.get("deductible"):
        score -= 2
    return score


def _fallback_compare(text1: str, text2: str, name1: str, name2: str):
    facts1 = _extract_policy_facts(text1)
    facts2 = _extract_policy_facts(text2)
    score1 = _value_score(facts1)
    score2 = _value_score(facts2)
    similarity = round(SequenceMatcher(None, _clean_text(text1)[:12000], _clean_text(text2)[:12000]).ratio() * 100)

    if abs(score1 - score2) <= 3:
        winner = "Tie"
        reason = f"Both policies look similar from extracted text. Text similarity is about {similarity}%."
    elif score1 > score2:
        winner = name1
        reason = f"{name1} exposes more useful coverage details and fewer obvious cost-sharing signals in the extracted text."
    else:
        winner = name2
        reason = f"{name2} exposes more useful coverage details and fewer obvious cost-sharing signals in the extracted text."

    def yes_no(value):
        return "Mentioned" if value else "Not found"

    rows = [
        {
            "aspect": "Document Similarity",
            "policy1": f"{similarity}% similar",
            "policy2": f"{similarity}% similar",
            "better": "Equal" if similarity >= 85 else "Needs manual review",
        },
        {
            "aspect": "Coverage / Sum Insured",
            "policy1": ", ".join(facts1["amounts"]) or "Not found",
            "policy2": ", ".join(facts2["amounts"]) or "Not found",
            "better": name1 if len(facts1["amounts"]) > len(facts2["amounts"]) else name2 if len(facts2["amounts"]) > len(facts1["amounts"]) else "Equal",
        },
        {
            "aspect": "Waiting Periods",
            "policy1": "; ".join(facts1["waiting_periods"]) or "Not found",
            "policy2": "; ".join(facts2["waiting_periods"]) or "Not found",
            "better": "Review required",
        },
        {
            "aspect": "Co-pay / Deductible",
            "policy1": yes_no(facts1["mentions"].get("co pay") or facts1["mentions"].get("deductible")),
            "policy2": yes_no(facts2["mentions"].get("co pay") or facts2["mentions"].get("deductible")),
            "better": name1 if not (facts1["mentions"].get("co pay") or facts1["mentions"].get("deductible")) and (facts2["mentions"].get("co pay") or facts2["mentions"].get("deductible")) else name2 if not (facts2["mentions"].get("co pay") or facts2["mentions"].get("deductible")) and (facts1["mentions"].get("co pay") or facts1["mentions"].get("deductible")) else "Equal",
        },
        {
            "aspect": "Claims / Cashless",
            "policy1": yes_no(facts1["mentions"].get("claim") or facts1["mentions"].get("cashless")),
            "policy2": yes_no(facts2["mentions"].get("claim") or facts2["mentions"].get("cashless")),
            "better": "Equal",
        },
        {
            "aspect": "Exclusions",
            "policy1": yes_no(facts1["mentions"].get("exclusion")),
            "policy2": yes_no(facts2["mentions"].get("exclusion")),
            "better": "Review required",
        },
    ]

    return {
        "winner": winner,
        "winner_reason": reason,
        "comparison_table": rows,
        "policy1_pros": ["Relevant coverage terms found", "Key numbers extracted" if facts1["amounts"] else "Readable text available"],
        "policy1_cons": ["Some clauses may need manual review", "AI provider fallback was used"],
        "policy2_pros": ["Relevant coverage terms found", "Key numbers extracted" if facts2["amounts"] else "Readable text available"],
        "policy2_cons": ["Some clauses may need manual review", "AI provider fallback was used"],
        "similarity_score": similarity,
        "important_note": "Fallback comparison is based on extracted text and keyword evidence because the AI provider did not return structured JSON.",
    }


# --------------------
# Public AI functions
# --------------------

def decode_policy(text: str):
    """Main policy decoder — returns structured JSON"""

    prompt = f"""You are an expert insurance analyst. Analyze this policy. Return ONLY valid JSON, no extra text.
{{
  "summary": "2-3 sentence plain English summary",
  "covered": ["what is covered, max 10 items"],
  "exclusions": ["what is NOT covered, max 10 items"],
  "hidden_traps": ["waiting periods, sub-limits, co-pays, traps"],
  "red_flags": ["critical things policyholder must know"],
  "health_score": 0-100,
  "health_reason": "one line reason for score",
  "recommended_questions": ["3 questions to ask the insurer"],
  "policy_type": "detected type e.g. Health/Term/ULIP",
  "key_numbers": {{"premium_range":"","coverage_amount":"","waiting_period":"","claim_ratio":""}}
}}
Policy (first 6000 chars): {text[:6000]}"""

    return ask_ai(prompt, json_mode=True)


def compare_policies(text1: str, text2: str, name1: str = "Policy A", name2: str = "Policy B"):
    """Compare two policies, return structured JSON"""

    facts1 = _extract_policy_facts(text1)
    facts2 = _extract_policy_facts(text2)
    context1 = _policy_context(text1, f"{name1} comparison benefits exclusions premium waiting periods")
    context2 = _policy_context(text2, f"{name2} comparison benefits exclusions premium waiting periods")

    prompt = f"""Compare these two insurance policies like a careful insurance analyst. Return ONLY valid JSON.
Do not guess. If a detail is missing, write "Not found in extracted text".
Pay special attention to small differences between similar PDFs, including sub-limits, waiting periods, co-pay, exclusions, premium value, claims, renewal, and room rent.
{{
  "winner": "{name1} or {name2} or Tie",
  "winner_reason": "specific reason with strongest evidence",
  "similarity_score": 0-100,
  "comparison_table": [
    {{"aspect":"Coverage / Sum Insured","policy1":"specific evidence","policy2":"specific evidence","better":"{name1} or {name2} or Equal or Review required"}},
    {{"aspect":"Premium Value","policy1":"specific evidence","policy2":"specific evidence","better":""}},
    {{"aspect":"Waiting Periods","policy1":"specific evidence","policy2":"specific evidence","better":""}},
    {{"aspect":"Sub-limits / Room Rent","policy1":"specific evidence","policy2":"specific evidence","better":""}},
    {{"aspect":"Co-pay / Deductible","policy1":"specific evidence","policy2":"specific evidence","better":""}},
    {{"aspect":"Exclusions","policy1":"specific evidence","policy2":"specific evidence","better":""}},
    {{"aspect":"Claim Process / Cashless","policy1":"specific evidence","policy2":"specific evidence","better":""}},
    {{"aspect":"Renewal / Portability","policy1":"specific evidence","policy2":"specific evidence","better":""}}
  ],
  "policy1_pros": ["max 3"],
  "policy1_cons": ["max 3"],
  "policy2_pros": ["max 3"],
  "policy2_cons": ["max 3"],
  "important_note": "short note on missing extracted details or similarity"
}}
Extracted facts for {name1}: {json.dumps(facts1, ensure_ascii=False)}
Extracted facts for {name2}: {json.dumps(facts2, ensure_ascii=False)}

Relevant sections from {name1}:
{context1[:12000]}

Relevant sections from {name2}:
{context2[:12000]}"""

    result = ask_ai(prompt, json_mode=True)
    if isinstance(result, dict):
        return result
    return _fallback_compare(text1, text2, name1, name2)


def assess_claim(policy_text: str, claim_description: str):
    """Estimate claim approval probability"""

    prompt = f"""Assess this insurance claim. Return ONLY valid JSON.
{{
  "approval_probability": 0-100,
  "verdict": "Likely Approved / Uncertain / Likely Rejected",
  "reasons_for": ["supporting reasons"],
  "reasons_against": ["rejection risks"],
  "advice": "what the claimant should do",
  "documents_needed": ["list of documents to submit"]
}}
Policy: {policy_text[:4000]}
Claim: {claim_description}"""

    return ask_ai(prompt, json_mode=True)


def get_negotiation_tips(policy_text: str, user_profile: str):
    """Generate premium negotiation tips"""

    prompt = f"""Generate specific insurance premium negotiation tips for this user.
Return ONLY valid JSON.
{{
  "tips": ["specific actionable tip 1", "tip 2", "tip 3", "tip 4", "tip 5"],
  "estimated_savings_percent": "X-Y%",
  "best_approach": "one paragraph strategy",
  "scripts": ["exact phrase to say to agent 1", "phrase 2"]
}}
Policy summary: {policy_text[:2000]}
User profile: {user_profile}"""

    return ask_ai(prompt, json_mode=True)


def generate_complaint_letter(policy_name, insurer_name, complaint_type, user_details):
    prompt = f"""
You are an expert insurance consumer advocate in India.

Write a formal complaint letter for the following situation:

Policy Name: {policy_name}
Insurance Company: {insurer_name}
Complaint Type: {complaint_type}
User Details: {user_details}

Write a professional, firm complaint letter addressed to the Insurance Company
and CC to IRDAI (Insurance Regulatory and Development Authority of India).

Include:
1. Clear subject line
2. Policy details section
3. Description of the complaint
4. What resolution is expected
5. Timeline given (15 days)
6. Mention of escalation to IRDAI if unresolved
7. Proper closing

Format as a ready-to-send letter.
"""
    return ask_ai(prompt)  # use whatever your existing AI call function is named

def analyze_coverage_gap(all_policies_text, user_profile):
    prompt = f"""
You are an expert insurance advisor in India.

The user has the following profile:
{user_profile}

They currently have these insurance policies:
{all_policies_text}

Analyze their coverage and identify:

1. COVERED RISKS — What risks are well covered
2. GAPS — What important risks are NOT covered at all
3. UNDERINSURED — Areas where coverage exists but is insufficient
4. PRIORITY RECOMMENDATIONS — Top 3 policies they should buy next (with estimated premium range in INR)
5. OVERALL COVERAGE SCORE — out of 100

Be specific and practical for an Indian user.
Return as structured analysis.
"""
    return ask_ai(prompt)

def calculate_premium_estimate(age, gender, smoker, bmi, policy_type, 
                                coverage_amount, city_tier, family_size):
    prompt = f"""
You are an insurance premium expert in India with knowledge of all major insurers.

Calculate a realistic premium estimate for:
- Age: {age}
- Gender: {gender}
- Smoker: {smoker}
- BMI: {bmi}
- Policy Type: {policy_type}
- Coverage Amount: ₹{coverage_amount}
- City Tier: {city_tier}
- Family Size: {family_size}

Provide:
1. ESTIMATED ANNUAL PREMIUM RANGE (min - max in INR)
2. TOP 3 RECOMMENDED INSURERS with their approximate premium
3. KEY FACTORS affecting your premium
4. TIPS to reduce premium
5. WHAT TO WATCH OUT FOR when buying

Be specific with INR amounts. Use current Indian market rates.
"""
    return ask_ai(prompt)

def ask_policy_question(policy_text: str, question: str, doc_id: int = None, policy_name: str = "your policy"):
    """Answer a question using the most relevant policy sections, not just the first page."""

    policy_text = policy_text or ""
    question = question or ""

    if not policy_text.strip():
        return "I could not read text from this policy. Please upload a clearer PDF or image."

    if doc_id:
        try:
            from .rag_engine import index_policy, get_relevant_chunks
            index_policy(doc_id, policy_text)
            relevant_text = get_relevant_chunks(doc_id, question)
        except Exception:
            relevant_text = _best_chunks(policy_text, question, limit=6)
    else:
        relevant_text = _best_chunks(policy_text, question, limit=6)

    relevant_text = relevant_text or _clean_text(policy_text)[:9000]

    prompt = f"""You are an Indian insurance expert. Answer ONLY from the policy text below.
If not in policy, say exactly: "This is not mentioned in your policy."
Be specific, name the policy, cite clause/section wording if visible, and explain in plain English.
If the question asks for a comparison or best option, give a short ranked answer with evidence.
Keep answer under 220 words.

Question: {question}
Policy: {policy_name}

Relevant Policy Sections:
{relevant_text[:12000]}"""

    answer = ask_ai(prompt, json_mode=False)
    return answer or "I could not get a reliable AI answer right now. The most relevant extracted text I found is: " + relevant_text[:700]


def ask_multi_policy_question(policies, question: str):
    """Answer a question across multiple policies using per-policy retrieval."""

    sections = []
    policy_evidence = []
    for policy in policies:
        name = getattr(policy, "name", "Policy")
        text = getattr(policy, "extracted_text", "") or ""
        if not text.strip():
            continue
        relevant = _best_chunks(text, question, limit=3) or _clean_text(text)[:3000]
        facts = _extract_policy_facts(text)
        preview = _clean_text(relevant)[:450]
        policy_evidence.append({
            "name": name,
            "facts": facts,
            "preview": preview,
        })
        sections.append(
            f"POLICY: {name}\nFACTS: {json.dumps(facts, ensure_ascii=False)}\nRELEVANT TEXT:\n{relevant[:5500]}"
        )

    if not sections:
        return "I could not find readable text in your uploaded policies."

    prompt = f"""You are an Indian insurance expert answering across multiple uploaded policies.
Use ONLY the evidence below. If a policy does not mention the answer, say that clearly.
For "best", "better", or comparison questions, compare the relevant policies in a compact table-like answer.
Always mention policy names.
Keep the answer practical and under 260 words.

Question: {question}

Policy evidence:
{chr(10).join(sections)[:18000]}"""

    answer = ask_ai(prompt, json_mode=False)
    if answer:
        return answer

    if policy_evidence:
        return _fallback_multi_answer(policy_evidence[:6], question)
    return "The AI provider did not return a response, and I could not find matching text in your uploaded policies."
