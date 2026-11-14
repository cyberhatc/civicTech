# Contributing to JanVaani UP

Thanks for helping a farmer find out about a scheme they qualify for.

## Getting set up

```powershell
.\scripts\setup.ps1
.\scripts\dev.ps1
```

The app runs **fully offline** — no API key is needed for development.

## Ground rules

1. **Never weaken a guardrail.** `backend/app/core/guardrails.py` masks Aadhaar and
   phone numbers in every log, prompt, payload and stored record. If a change would
   let a raw identifier through, it will be rejected in review.
2. **Every AI call needs an offline twin.** A new Groq call must have a deterministic
   fallback in the same module, so the demo works with no key and no network.
3. **Answers stay grounded.** A rupee amount or eligibility criterion may only reach
   the user if it exists in a retrieved chunk. Do not hard-code amounts in prompts.
4. **Add a test.** `backend/tests/` has a suite for the retriever, the NLU, the
   guardrails and every API route. Run it before you push:

   ```powershell
   .\.venv\Scripts\python.exe -m pytest backend\tests -q
   ```

## Adding a scheme

Append an entry to `backend/app/data/schemes.json`:

```json
{
  "id": "scheme-id",
  "name": "Official English name",
  "name_hi": "देवनागरी नाम",
  "short_name": "SHORT",
  "category": "agriculture",
  "category_hi": "कृषि",
  "authority": "Which ministry or department",
  "state": "All India / Uttar Pradesh",
  "summary": "One paragraph in English",
  "summary_hi": "एक अनुच्छेद हिंदी में",
  "amount": "Rs 6,000 per year",
  "amounts": ["2000", "6000"],
  "icon": "🌾",
  "tags": ["kisan", "zameen", "bigha"],
  "sections": [
    {
      "id": "scheme-id.eligibility",
      "title": "Eligibility Criteria",
      "title_hi": "पात्रता मानदंड",
      "body": "English text of the clause",
      "body_hi": "हिंदी में शर्त",
      "eligibility": ["..."],
      "eligibility_hi": ["..."],
      "documents": ["..."],
      "documents_hi": ["..."],
      "source": "official.gov.in",
      "page": 2
    }
  ]
}
```

The retriever, the citations and the UI pick it up with **no code change**.

## Adding a dialect word

Add it to the relevant list in `backend/app/data/synonyms.json`:

* `intents` — phrases that signal an intent
* `category_map` — words that place a grievance in a department
* `entities.district` — any UP district name
* `lang_markers` — words that identify Bhojpuri / Awadhi

## Commit messages

Short and imperative: `fix: mask phone numbers before storing a ticket`.
