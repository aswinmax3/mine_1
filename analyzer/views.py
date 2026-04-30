from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from .ml.prediction_engine import predict_expected_cost, calculate_real_life_risk

from .models import InsuranceDocument
from .forms import InsuranceDocumentForm

from .ml.ocr_processor import extract_text_from_document
from .ml.nlp_extractor import extract_all_details
from .ml.document_classifier import classify_document
from .ml.recommender import generate_recommendation


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')

    else:
        form = UserCreationForm()

    return render(request, 'analyzer/register.html', {'form': form})


@login_required
def dashboard(request):
    documents = InsuranceDocument.objects.all().order_by('-uploaded_at')

    context = {
        'documents': documents,
        'total_documents': documents.count(),
        'policy_count': documents.filter(document_type='policy').count(),
        'claim_count': documents.filter(document_type='claim').count(),
        'high_risk_count': documents.filter(risk_level='High').count(),
    }

    return render(request, 'analyzer/dashboard.html', context)


@login_required
def upload_document(request):
    if request.method == 'POST':
        form = InsuranceDocumentForm(request.POST, request.FILES)

        if form.is_valid():
            insurance_doc = form.save()

            file_path = insurance_doc.document.path
            extracted_text = extract_text_from_document(file_path)
            document_type = classify_document(extracted_text)
            extracted_details = extract_all_details(extracted_text)
            prediction_result = predict_expected_cost(
                age=insurance_doc.age,
                sex=insurance_doc.sex,
                bmi=insurance_doc.bmi,
                children=insurance_doc.children,
                smoker=insurance_doc.smoker,
                region=insurance_doc.region
            )

            predicted_cost = prediction_result["predicted_cost"]

            ml_risk_level = calculate_real_life_risk(
                predicted_cost=predicted_cost,
                coverage_amount=extracted_details['coverage_amount'],
                premium_amount=extracted_details['premium_amount']
            )

            recommendation_data = generate_recommendation(
                document_type=document_type,
                premium=extracted_details['premium_amount'],
                coverage=extracted_details['coverage_amount'],
                exclusions=extracted_details['exclusions'],
                claim_terms=extracted_details['claim_terms'],
                predicted_cost=predicted_cost,
                ml_risk_level=ml_risk_level
            )

            insurance_doc.extracted_text = extracted_text
            insurance_doc.document_type = document_type
            insurance_doc.policy_number = extracted_details['policy_number']
            insurance_doc.premium_amount = extracted_details['premium_amount']
            insurance_doc.coverage_amount = extracted_details['coverage_amount']
            insurance_doc.exclusions = extracted_details['exclusions']
            insurance_doc.claim_terms = extracted_details['claim_terms']
            insurance_doc.recommendation = recommendation_data['recommendation']
            insurance_doc.risk_level = recommendation_data['risk_level']
            insurance_doc.predicted_cost = predicted_cost
            insurance_doc.save()

            return redirect('result', pk=insurance_doc.pk)

    else:
        form = InsuranceDocumentForm()

    return render(request, 'analyzer/upload.html', {'form': form})


@login_required
def result(request, pk):
    document = get_object_or_404(InsuranceDocument, pk=pk)
    return render(request, 'analyzer/result.html', {'document': document})


@login_required
def recommendations(request):
    documents = InsuranceDocument.objects.all().order_by('-uploaded_at')

    return render(request, 'analyzer/recommendations.html', {
        'documents': documents
    })