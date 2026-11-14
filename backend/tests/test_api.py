"""API-level tests covering the three citizen flows and the officer dashboard."""

from __future__ import annotations

import json


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["service"] == "janvaani-up"
    assert data["database"]["seeded"] is True
    assert data["vector"]["schemes"] >= 8


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "JanVaani UP"


def test_schemes_list(client):
    response = client.get("/api/schemes")
    assert response.status_code == 200
    schemes = response.json()["data"]["schemes"]
    assert len(schemes) >= 8
    assert all("shortName" in scheme for scheme in schemes)


def test_scheme_detail(client):
    response = client.get("/api/schemes/pm-kisan")
    assert response.status_code == 200
    scheme = response.json()["data"]["scheme"]
    assert scheme["id"] == "pm-kisan"
    assert scheme["sections"]


def test_scheme_detail_404(client):
    assert client.get("/api/schemes/nope").status_code == 404


def test_scheme_search_is_grounded(client):
    response = client.post("/api/schemes/search", json={"query": "2 bigha zameen kisan"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["answer"]
    assert data["citations"]
    assert data["citations"][0]["source"]


def test_chat_scheme_eligibility(client):
    response = client.post(
        "/api/chat/text", json={"text": "Hamre paas 2 bigha zameen ba, kaun sarkari yojana mili?", "speak": False}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"]["name"] == "scheme_eligibility"
    assert data["intent"]["entities"]["landBigha"] == 2
    assert data["reply"]["text"]
    assert data["citations"]
    # The top citation must be the eligibility criteria, not the exclusions.
    assert data["citations"][0]["sectionId"].endswith("eligibility")


def test_chat_answer_states_the_eligibility_criteria(client):
    response = client.post(
        "/api/chat/text", json={"text": "kaun sa yojana milegi mujhe", "speak": False}
    )
    reply = response.json()["data"]["reply"]["text"]
    assert "पात्रता" in reply or "eligible" in reply.lower()


def test_chat_greeting(client):
    response = client.post("/api/chat/text", json={"text": "नमस्ते", "speak": False})
    assert response.json()["data"]["intent"]["name"] == "greeting"


def test_grievance_multi_turn_creates_a_ticket(client):
    session = None

    first = client.post(
        "/api/chat/text",
        json={
            "text": "Hamare gaon ke transformer 4 din se jala pada hai, koi sun nahi raha.",
            "speak": False,
        },
    ).json()["data"]
    session = first["sessionId"]
    assert first["intent"]["name"] == "grievance_file"
    assert first["intent"]["entities"]["category"] == "electricity"
    assert first["awaiting"]

    second = client.post(
        "/api/chat/text", json={"text": "Barabanki", "sessionId": session, "speak": False}
    ).json()["data"]
    session = second["sessionId"]

    third = client.post(
        "/api/chat/text",
        json={"text": "Tanda block, Bansipur gaon", "sessionId": session, "speak": False},
    ).json()["data"]
    session = third["sessionId"]

    fourth = client.post(
        "/api/chat/text", json={"text": "9876543210", "sessionId": session, "speak": False}
    ).json()["data"]

    tickets = fourth["tickets"]
    assert len(tickets) == 1
    ticket = tickets[0]
    assert ticket["id"].startswith("JVUP-")
    assert ticket["district"] == "Barabanki"
    assert ticket["village"] == "Bansipur"
    assert ticket["category"] == "electricity"
    assert ticket["summary"]
    # The raw phone number must not appear anywhere in the stored ticket.
    assert "9876543210" not in json.dumps(ticket, ensure_ascii=False)


def test_grievance_skip_contact(client):
    first = client.post(
        "/api/chat/text",
        json={"text": "gaon me paani nahi aa raha 3 din se", "speak": False},
    ).json()["data"]
    session = first["sessionId"]

    second = client.post(
        "/api/chat/text", json={"text": "Barabanki", "sessionId": session, "speak": False}
    ).json()["data"]
    session = second["sessionId"]

    third = client.post(
        "/api/chat/text",
        json={"text": "Bansipur gaon Tanda block", "sessionId": session, "speak": False},
    ).json()["data"]
    session = third["sessionId"]

    fourth = client.post(
        "/api/chat/text", json={"text": "skip", "sessionId": session, "speak": False}
    ).json()["data"]

    assert fourth["tickets"], "skipping the contact should still file the grievance"


def test_status_flow_asks_for_identifier(client):
    response = client.post(
        "/api/chat/text",
        json={"text": "Mera ration card ya PM Kisan ka paisa kahan tak pahuncha?", "speak": False},
    )
    data = response.json()["data"]
    assert data["intent"]["name"] == "status_track"
    assert data["awaiting"] == "status_identifier"


def test_lookup_by_aadhaar(client):
    response = client.get("/api/applications/lookup?aadhaarLast4=4821")
    data = response.json()["data"]
    assert data["found"] is True
    assert data["applications"]
    assert data["citizen"]["aadhaar"].startswith("XXXX-XXXX-")


def test_lookup_by_mobile(client):
    data = client.get("/api/applications/lookup?mobile=9876543210").json()["data"]
    assert data["found"] is True


def test_lookup_unknown(client):
    data = client.get("/api/applications/lookup?aadhaarLast4=0000").json()["data"]
    assert data["found"] is False
    assert data["applications"] == []


def test_tickets_list_and_update(client):
    listing = client.get("/api/tickets").json()["data"]
    assert listing["total"] > 0
    ticket_id = listing["tickets"][0]["id"]

    updated = client.patch(f"/api/tickets/{ticket_id}", json={"status": "RESOLVED"})
    assert updated.status_code == 200
    assert updated.json()["data"]["ticket"]["status"] == "RESOLVED"

    # Resolving it must be reflected in the dashboard counters.
    stats = client.get("/api/admin/stats").json()["data"]["stats"]
    assert stats["totals"]["resolved"] >= 1


def test_ticket_update_rejects_bad_status(client):
    ticket_id = client.get("/api/tickets").json()["data"]["tickets"][0]["id"]
    assert client.patch(f"/api/tickets/{ticket_id}", json={"status": "NONSENSE"}).status_code == 400


def test_ticket_note(client):
    ticket_id = client.get("/api/tickets").json()["data"]["tickets"][0]["id"]
    response = client.patch(f"/api/tickets/{ticket_id}", json={"note": "Team dispatched"})
    assert response.status_code == 200
    notes = response.json()["data"]["ticket"]["notes"]
    assert notes and notes[-1]["note"] == "Team dispatched"


def test_admin_stats_shape(client):
    data = client.get("/api/admin/stats").json()["data"]
    stats = data["stats"]
    assert stats["totals"]["tickets"] > 0
    assert len(stats["timeline"]) == 14
    assert stats["byCategory"]
    assert data["feed"]


def test_session_history(client):
    first = client.post("/api/chat/text", json={"text": "namaste", "speak": False}).json()["data"]
    session = first["sessionId"]
    history = client.get(f"/api/voice/session/{session}").json()["data"]
    assert history["exists"] is True
    assert history["turns"]


def test_voice_turn_with_text_only(client):
    response = client.post(
        "/api/voice/turn", data={"text": "kaun si yojana milegi", "lang": "hi"}, files={}
    )
    assert response.status_code == 200
    assert response.json()["data"]["reply"]["text"]


def test_whatsapp_webhook(client):
    payload = {
        "entry": [
            {
                "changes": [
                    {"value": {"messages": [{"from": "919876543210", "text": {"body": "paani nahi hai"}}]}}
                ]
            }
        ]
    }
    response = client.post("/api/whatsapp/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["data"]["replies"]


def test_whatsapp_verify(client):
    response = client.get("/api/whatsapp/verify", params={"hub.challenge": "abc123", "hub.verify_token": "janvaani_up_verify_token"})
    assert response.status_code == 200
    assert response.text == "abc123"
