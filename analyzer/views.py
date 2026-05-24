import io
import json

import pdfplumber
import pytesseract
from PIL import Image
from django.conf import settings
print("GEMINI KEY LOADED:", settings.GEMINI_API_KEY)

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import PolicyDocument, ChatMessage, ClaimAssessment
from .ml.ai_engine import (
    decode_policy,
    compare_policies,
    ask_policy_question,
    assess_claim,
    get_negotiation_tips,
)


def extract_text(file_obj):
    """Extract text from PDF or image"""

    name = file_obj.name.lower()
    if name.endswith('.pdf'):
        text = ""
        with pdfplumber.open(file_obj) as pdf:
            for page in pdf.pages[:20]:  # max 20 pages
                text += (page.extract_text() or "") + "\n"
        return text.strip()

    # image
    img = Image.open(file_obj)
    return pytesseract.image_to_string(img)


def index(request):
    docs = PolicyDocument.objects.filter(
        user=request.user if request.user.is_authenticated else None
    ).order_by('-uploaded_at')[:6]
    return render(request, 'analyzer/index.html', {'docs': docs})


def upload_policy(request):
    if request.method == 'POST':
        f = request.FILES.get('policy_file')
        if not f:
            return render(request, 'analyzer/upload.html', {'error': 'No file uploaded'})

        text = extract_text(f)
        f.seek(0)

        doc = PolicyDocument.objects.create(
            user=request.user if request.user.is_authenticated else None,
            name=f.name,
            file=f,
            extracted_text=text,
        )

        analysis = decode_policy(text)
        if analysis:
            doc.ai_analysis = analysis
            doc.health_score = analysis.get('health_score', 50)
            doc.save()

        return redirect('policy_dashboard', pk=doc.pk)

    return render(request, 'analyzer/upload.html')


def policy_dashboard(request, pk):
    doc = get_object_or_404(PolicyDocument, pk=pk)
    return render(request, 'analyzer/dashboard.html', {'doc': doc})


def policy_chat(request, pk):
    doc = get_object_or_404(PolicyDocument, pk=pk)
    messages = doc.messages.order_by('created_at')
    return render(request, 'analyzer/chat.html', {'doc': doc, 'messages': messages})


@require_POST
def chat_ask(request, pk):
    doc = get_object_or_404(PolicyDocument, pk=pk)
    question = request.POST.get('question', '').strip()

    if not question:
        return JsonResponse({'error': 'Empty question'}, status=400)

    ChatMessage.objects.create(policy=doc, role='user', content=question)
    answer = ask_policy_question(doc.extracted_text or '', question) or ''
    ChatMessage.objects.create(policy=doc, role='ai', content=answer)

    return JsonResponse({'answer': answer})


def compare_view(request):
    if request.method == 'POST':
        f1 = request.FILES.get('policy1')
        f2 = request.FILES.get('policy2')
        if not f1 or not f2:
            return render(request, 'analyzer/compare.html', {'error': 'Upload 2 files'})

        t1 = extract_text(f1)
        t2 = extract_text(f2)
        result = compare_policies(t1, t2, f1.name, f2.name)

        return render(
            request,
            'analyzer/compare_result.html',
            {'result': result, 'name1': f1.name, 'name2': f2.name},
        )

    return render(request, 'analyzer/compare.html')


def claim_check(request, pk):
    doc = get_object_or_404(PolicyDocument, pk=pk)
    if request.method == 'POST':
        desc = request.POST.get('claim_description', '')
        result = assess_claim(doc.extracted_text or '', desc) or {}
        ClaimAssessment.objects.create(policy=doc, claim_description=desc, result=result)
        return render(request, 'analyzer/claim_result.html', {'result': result, 'doc': doc})

    return render(request, 'analyzer/claim_check.html', {'doc': doc})


def negotiation_tips(request, pk):
    doc = get_object_or_404(PolicyDocument, pk=pk)
    if request.method == 'POST':
        profile = request.POST.get('profile', '')
        tips = get_negotiation_tips(doc.extracted_text or '', profile) or {}
        return render(request, 'analyzer/negotiation.html', {'tips': tips, 'doc': doc})

    return render(request, 'analyzer/negotiation_form.html', {'doc': doc})


def recommend_view(request):
    """Keep existing ML recommender."""

    from .ml.advanced_recommender import get_policy_recommendations

    if request.method == 'POST':
        data = request.POST
        recs = get_policy_recommendations(
            age=int(data.get('age', 30)),
            gender=data.get('gender', 'male'),
            bmi=float(data.get('bmi', 24)),
            smoker=data.get('smoker', 'no'),
            income=int(data.get('income', 500000)),
            family_size=int(data.get('family_size', 2)),
            coverage_needed=int(data.get('coverage', 2000000)),
            budget_max=int(data.get('budget', 30000)),
        )
        return render(request, 'analyzer/recommendations.html', {'recs': recs})

    return render(request, 'analyzer/recommend_form.html')

