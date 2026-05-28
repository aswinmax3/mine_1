import io
import json
from xml.sax.saxutils import escape

import pdfplumber
import pytesseract
from PIL import Image
from .email_utils import send_verification_email, send_coverage_gap_email

from django.conf import settings
print("GEMINI KEY LOADED:", settings.GEMINI_API_KEY)

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import PolicyDocument, ChatMessage, ClaimAssessment
from .ml.ai_engine import (
    decode_policy,
    compare_policies,
    ask_policy_question,
    assess_claim,
    get_negotiation_tips,
)


def home(request):
    """Home page - landing page for unauthenticated users."""
    if request.user.is_authenticated:
        return redirect('index')
    return render(request, 'analyzer/home.html')


def login_view(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect('index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            return render(request, 'analyzer/login.html', {'error': 'Invalid username or password'})
    
    return render(request, 'analyzer/login.html')


def register_view(request):
    """User registration view."""
    if request.user.is_authenticated:
        return redirect('index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        if not username or not password1 or not password2:
            return render(request, 'analyzer/register.html', {'error': 'All fields are required'})
        
        if password1 != password2:
            return render(request, 'analyzer/register.html', {'error': 'Passwords do not match'})
        
        if User.objects.filter(username=username).exists():
            return render(request, 'analyzer/register.html', {'error': 'Username already exists'})
        
        user = User.objects.create_user(username=username, password=password1)
        login(request, user)
        return redirect('index')
    
    return render(request, 'analyzer/register.html')


def logout_view(request):
    """User logout view."""
    logout(request)
    return redirect('home')


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
        expiry_date = request.POST.get('expiry_date') or None

        if not f:
            return render(request, 'analyzer/upload.html', {'error': 'No file uploaded'})

        text = extract_text(f)
        f.seek(0)

        doc = PolicyDocument.objects.create(
            user=request.user if request.user.is_authenticated else None,
            name=f.name,
            file=f,
            extracted_text=text,
            expiry_date=expiry_date,
        )

        analysis = decode_policy(text)
        if analysis:
            doc.ai_analysis = analysis
            doc.health_score = analysis.get('health_score', 50)
            doc.save()

        # Send verification email
        try:
            send_verification_email(request.user, doc)  # FIXED: 'document' → 'doc'
        except Exception as e:
            print(f"Email error: {e}")

        return redirect('policy_dashboard', pk=doc.pk)  # FIXED: removed the dead redirect above this

    return render(request, 'analyzer/upload.html')
def policy_dashboard(request, pk):
    doc = get_object_or_404(PolicyDocument, pk=pk)
    return render(request, 'analyzer/dashboard.html', {'doc': doc})


def _pdf_text(value, fallback='N/A'):
    if value is None or value == '':
        return fallback
    if isinstance(value, (list, tuple)):
        return '<br/>'.join(escape(str(item)) for item in value) or fallback
    if isinstance(value, dict):
        return '<br/>'.join(f'{escape(str(key))}: {escape(str(val))}' for key, val in value.items()) or fallback
    return escape(str(value))


def download_policy_pdf(request, pk):
    doc = get_object_or_404(PolicyDocument, pk=pk)
    analysis = doc.ai_analysis or {}

    buffer = io.BytesIO()
    safe_name = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in doc.name)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{safe_name}_analysis.pdf"'

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    heading_style = styles['Heading2']
    body_style = styles['BodyText']

    story = [
        Paragraph('Insurance Policy Analysis Report', title_style),
        Spacer(1, 12),
        Paragraph(f'<b>Document:</b> {_pdf_text(doc.name)}', body_style),
        Paragraph(f'<b>Uploaded:</b> {doc.uploaded_at.strftime("%d %b %Y, %I:%M %p")}', body_style),
        Spacer(1, 14),
    ]

    summary_rows = [
        ['Policy Type', _pdf_text(analysis.get('policy_type'), 'Policy')],
        ['Health Score', _pdf_text(doc.health_score)],
        ['Health Reason', _pdf_text(analysis.get('health_reason'))],
    ]
    table = Table(summary_rows, colWidths=[1.8 * inch, 4.6 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#EEF2FF')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1F2937')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.extend([table, Spacer(1, 16)])

    sections = [
        ('Plain English Summary', analysis.get('summary')),
        ('Key Numbers', analysis.get('key_numbers')),
        ("What's Covered", analysis.get('covered')),
        ('Exclusions', analysis.get('exclusions')),
        ('Red Flags', analysis.get('red_flags')),
        ('Hidden Traps', analysis.get('hidden_traps')),
        ('Questions to Ask Your Insurer', analysis.get('recommended_questions')),
    ]

    for heading, value in sections:
        story.append(Paragraph(heading, heading_style))
        story.append(Paragraph(_pdf_text(value), body_style))
        story.append(Spacer(1, 10))

    extracted_text = (doc.extracted_text or '').strip()
    if extracted_text:
        story.append(Paragraph('Extracted Text Preview', heading_style))
        preview = extracted_text[:3500]
        if len(extracted_text) > len(preview):
            preview += '...'
        story.append(Paragraph(_pdf_text(preview).replace('\n', '<br/>'), body_style))

    pdf.build(story)
    response.write(buffer.getvalue())
    buffer.close()
    return response


def policy_chat(request, pk):
    doc = get_object_or_404(PolicyDocument, pk=pk)
    messages = doc.messages.order_by('created_at')
    return render(request, 'analyzer/chat.html', {'doc': doc, 'messages': messages})


@login_required
def delete_policy(request, pk):
    """Delete a policy document."""
    doc = get_object_or_404(PolicyDocument, pk=pk)
    
    # Check if the user owns the policy
    if doc.user != request.user:
        return redirect('index')
    
    doc.delete()
    return redirect('index')


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

def complaint_letter(request, pk):
    doc = get_object_or_404(PolicyDocument, pk=pk)
    
    if request.method == 'POST':
        insurer_name = request.POST.get('insurer_name', '')
        complaint_type = request.POST.get('complaint_type', '')
        user_details = request.POST.get('user_details', '')
        
        from .ml.ai_engine import generate_complaint_letter
        letter = generate_complaint_letter(
            policy_name=doc.name,
            insurer_name=insurer_name,
            complaint_type=complaint_type,
            user_details=user_details,
        )
        return render(request, 'analyzer/complaint_result.html', {
            'letter': letter, 'doc': doc
        })
    
    return render(request, 'analyzer/complaint_form.html', {'doc': doc})

@login_required
def coverage_gap(request):
    user_docs = PolicyDocument.objects.filter(user=request.user)
    
    if request.method == 'POST':
        # Combine all policy texts
        all_text = "\n\n---\n\n".join([
            f"Policy: {doc.name}\n{doc.extracted_text[:2000]}"
            for doc in user_docs
        ])
        
        profile = {
            'age': request.POST.get('age'),
            'family_size': request.POST.get('family_size'),
            'income': request.POST.get('income'),
            'has_home': request.POST.get('has_home'),
            'has_vehicle': request.POST.get('has_vehicle'),
            'chronic_illness': request.POST.get('chronic_illness'),
        }
        
        from .ml.ai_engine import analyze_coverage_gap
        result = analyze_coverage_gap(all_text, str(profile))
        try:
            send_coverage_gap_email(request.user, str(result))
        except Exception as e:
            print(f"Email error: {e}")
        
        return render(request, 'analyzer/coverage_gap_result.html', {
            'result': result,
            'docs': user_docs,
        })

        
        return render(request, 'analyzer/coverage_gap_result.html', {
            'result': result,
            'docs': user_docs,
        })
    
    return render(request, 'analyzer/coverage_gap_form.html', {'docs': user_docs})

@login_required
def multi_policy_chat(request):
    docs = PolicyDocument.objects.filter(user=request.user)
    return render(request, 'analyzer/multi_chat.html', {'docs': docs})


@require_POST
@login_required
def multi_policy_ask(request):
    question = request.POST.get('question', '').strip()
    if not question:
        return JsonResponse({'error': 'Empty question'}, status=400)

    docs = PolicyDocument.objects.filter(user=request.user)
    combined_text = "\n\n---\n\n".join([
        f"POLICY: {doc.name}\n{(doc.extracted_text or '')[:3000]}"
        for doc in docs
    ])

    prompt = f"""
The user has these insurance policies:

{combined_text}

Answer this question by referring to the relevant policy:
{question}

If multiple policies are relevant, mention which policy covers what.
If nothing covers the question, say so clearly.
"""
    answer = ask_policy_question(combined_text, question) or 'Sorry, I could not find an answer.'
    return JsonResponse({'answer': answer})

def premium_calculator(request):
    if request.method == 'POST':
        data = request.POST
        
        from .ml.ai_engine import calculate_premium_estimate
        result = calculate_premium_estimate(
            age=data.get('age'),
            gender=data.get('gender'),
            smoker=data.get('smoker'),
            bmi=data.get('bmi'),
            policy_type=data.get('policy_type'),
            coverage_amount=data.get('coverage_amount'),
            city_tier=data.get('city_tier'),
            family_size=data.get('family_size'),
        )
        return render(request, 'analyzer/premium_result.html', {'result': result, 'data': data})
    
    return render(request, 'analyzer/premium_form.html')
@login_required
def profile_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '')
        request.user.email = email
        request.user.save()
        return render(request, 'analyzer/profile.html', {
            'success': 'Profile updated successfully!',
            'policy_count': PolicyDocument.objects.filter(user=request.user).count(),
            'claim_count': ClaimAssessment.objects.filter(policy__user=request.user).count(),
        })
    return render(request, 'analyzer/profile.html', {
        'policy_count': PolicyDocument.objects.filter(user=request.user).count(),
        'claim_count': ClaimAssessment.objects.filter(policy__user=request.user).count(),
    })

@require_POST
def set_expiry(request, pk):
    doc = get_object_or_404(PolicyDocument, pk=pk)
    expiry_date = request.POST.get('expiry_date') or None
    doc.expiry_date = expiry_date
    doc.save()
    return redirect('policy_dashboard', pk=pk)