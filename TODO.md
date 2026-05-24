# TODO - Insurance AI Upgrade (Gemini/Groq/OpenRouter Policy Decoder)

## Step 1: Dependencies & env
- [x] Update `requirements.txt` with AI packages
- [x] Create `.env` with GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY placeholders

## Step 2: Django settings
- [x] Update `insurance_ai/settings.py` to load dotenv and expose API keys
- [x] Ensure media settings remain correct
- [x] Update `TEMPLATES[0]['DIRS']` to include `BASE_DIR / 'templates'`

## Step 3: AI engine
- [x] Create `analyzer/ml/ai_engine.py` (Gemini → Groq → OpenRouter fallback + JSON decoding)

## Step 4: Models
- [x] Update `analyzer/models.py` with `PolicyDocument`, `ChatMessage`, `ClaimAssessment`

## Step 5: Views & URLs
- [x] Replace/extend `analyzer/views.py` with new AI decoder workflow views
- [x] Replace `analyzer/urls.py` routes to match the new workflow

## Step 6: Templates
- [x] Create new Tailwind templates under `analyzer/templates/analyzer/`

## Step 7: Migrations & run
- [ ] Run `python manage.py makemigrations analyzer`
- [ ] Run `python manage.py migrate`
- [ ] Run `python manage.py runserver` and verify routes

