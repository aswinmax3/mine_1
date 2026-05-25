import os
import json
import time
import re

import httpx

from django.conf import settings


# --------------------
# Gemini / Groq / OpenRouter clients (lazy imports)
# --------------------

def _init_clients():
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    gemini = None
    if getattr(settings, "GEMINI_API_KEY", None):
        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.GEMINI_API_KEY)
            gemini = genai.GenerativeModel(gemini_model)
        except Exception:
            gemini = None

    groq_client = None
    if getattr(settings, "GROQ_API_KEY", None):
        try:
            from groq import Groq

            groq_client = Groq(api_key=settings.GROQ_API_KEY)
        except Exception:
            groq_client = None

    openrouter_key = getattr(settings, "OPENROUTER_API_KEY", None)
    return gemini, groq_client, openrouter_key



_GEMINI, _GROQ_CLIENT, _OPENROUTER_KEY = _init_clients()


def _safe_json_loads(text: str):
    # Remove code fences if any
    text = text.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    # If model returns extra text, try to extract first JSON object/array
    if not text.startswith("{") and not text.startswith("["):
        m = re.search(r"({[\s\S]*}|\[[\s\S]*\])", text)
        if m:
            text = m.group(1)

    return json.loads(text)


def _call_gemini(prompt: str) -> str:
    if _GEMINI is None:
        raise RuntimeError("GEMINI_API_KEY not configured")
    r = _GEMINI.generate_content(prompt)
    return getattr(r, "text", None) or str(r)


def _call_groq(prompt: str) -> str:
    if _GROQ_CLIENT is None:
        raise RuntimeError("GROQ_API_KEY not configured")

    r = _GROQ_CLIENT.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
    )
    return r.choices[0].message.content


def _call_openrouter(prompt: str) -> str:
    if not _OPENROUTER_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not configured")

    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {_OPENROUTER_KEY}"},
        json={
            "model": "mistralai/mistral-7b-instruct:free",
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]


def ask_ai(prompt: str, json_mode: bool = False):
    """Fallback chain: Gemini → Groq → OpenRouter"""

    fns = [_call_gemini, _call_groq, _call_openrouter]
    last_err = None

    for fn in fns:
        try:
            result = fn(prompt)
            if json_mode:
                return _safe_json_loads(result)
            return result
        except Exception as e:
            last_err = e
            # small backoff to avoid hammering
            time.sleep(0.6)

    if last_err:
        return None
    return None


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

    prompt = f"""Compare these two insurance policies. Return ONLY valid JSON.
{{
  "winner": "{name1} or {name2} or Tie",
  "winner_reason": "one line",
  "comparison_table": [
    {{"aspect":"Coverage","policy1":"...","policy2":"...","better":"{name1} or {name2} or Equal"}},
    {{"aspect":"Exclusions","policy1":"...","policy2":"...","better":""}},
    {{"aspect":"Premium Value","policy1":"...","policy2":"...","better":""}},
    {{"aspect":"Waiting Period","policy1":"...","policy2":"...","better":""}},
    {{"aspect":"Claim Process","policy1":"...","policy2":"...","better":""}},
    {{"aspect":"Hidden Traps","policy1":"...","policy2":"...","better":""}}
  ],
  "policy1_pros": ["max 3"],
  "policy1_cons": ["max 3"],
  "policy2_pros": ["max 3"],
  "policy2_cons": ["max 3"]
}}
{name1} (first 3000 chars): {text1[:3000]}
{name2} (first 3000 chars): {text2[:3000]}"""

    return ask_ai(prompt, json_mode=True)


def ask_policy_question(policy_text: str, question: str):
    """Chatbot: answer user question from policy text"""

    prompt = f"""You are an insurance expert. Answer this question based ONLY on the policy below.
If not covered in policy, say "This is not mentioned in your policy."
Be concise, clear, helpful. No jargon.
Question: {question}
Policy (first 5000 chars): {policy_text[:5000]}"""

    return ask_ai(prompt, json_mode=False)


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