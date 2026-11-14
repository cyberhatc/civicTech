"""Dialect NLU tests - Hindi, Bhojpuri, Awadhi and Hinglish must all be understood."""

from __future__ import annotations

from app.services import nlu


def analyze(text: str) -> nlu.Intent:
    return nlu.lexicon_analyze(text)


def test_bhojpuri_land_eligibility():
    intent = analyze("Hamre paas 2 bigha zameen ba, kaun sarkari yojana mili?")
    assert intent.name == "scheme_eligibility"
    assert intent.entities.get("landBigha") == 2
    assert intent.language in ("bho", "hin", "awd")


def test_bhojpuri_transformer_complaint():
    intent = analyze("Hamare gaon ke transformer 4 din se jala pada hai, koi sun nahi raha.")
    assert intent.name == "grievance_file"
    assert intent.entities.get("category") == "electricity"
    assert intent.entities.get("durationDays") == 4
    assert intent.entities.get("urgency") == "high"


def test_awadhi_water_complaint():
    intent = analyze("Haman gaon me paani nahi aa raha, bijli bhi nahi")
    assert intent.entities.get("category") in ("water", "electricity")


def test_status_question_is_not_treated_as_eligibility():
    intent = analyze("Mera ration card ya PM Kisan ka paisa kahan tak pahuncha?")
    assert intent.name == "status_track"


def test_greeting():
    assert analyze("नमस्ते जी").name == "greeting"


def test_scheme_documents_intent():
    assert analyze("PM Awas ke liye kaun kaun se document chahiye").name == "scheme_documents"


def test_scheme_list_intent():
    assert analyze("सभी योजनाओं की लिस्ट दिखाओ").name == "scheme_list"


def test_contact_human_intent():
    assert analyze("kisi se baat karwao insaan se").name == "contact_human"


def test_help_intent():
    assert analyze("madad chahiye, kya kar sakte ho").name == "help"


def test_district_extraction():
    intent = analyze("Barabanki")
    assert intent.entities.get("district") == "Barabanki"


def test_block_and_village_extraction():
    intent = analyze("Tanda block, Bansipur gaon")
    assert intent.entities.get("block") == "Tanda"
    assert intent.entities.get("village") == "Bansipur"


def test_pronouns_are_not_places():
    intent = analyze("Hamare gaon ke transformer jala pada hai")
    assert intent.entities.get("village") is None


def test_mobile_number_extraction():
    intent = analyze("mera number 9876543210 hai")
    assert intent.entities.get("mobile") == "9876543210"


def test_aadhaar_last_four_extraction():
    intent = analyze("mera aadhaar 4123 5678 4821 hai")
    assert intent.entities.get("aadhaarLast4") == "4821"


def test_sentiment_detection():
    assert analyze("koi nahi sun raha, bahut problem hai").entities.get("sentiment") == "negative"


def test_language_detection_bhojpuri():
    intent = analyze("hamare gaon me bijli nahi aa rahi hai")
    assert intent.language in ("bho", "hin")


def test_unknown_still_returns_entities():
    intent = analyze("Barabanki")
    assert intent.name == "unknown"
    assert intent.entities.get("district") == "Barabanki"


def test_all_intent_names_are_known():
    for text in [
        "namaste",
        "kaun si yojana milegi",
        "document chahiye",
        "sabhi yojana",
        "shikayat hai transformer jala",
        "paisa kab aayega",
        "helpline chahiye",
        "help",
        "xyzzy",
    ]:
        assert analyze(text).name in nlu.INTENTS
