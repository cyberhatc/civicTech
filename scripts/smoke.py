"""End-to-end smoke test against a running JanVaani UP server.

Usage:
    py scripts/smoke.py [base_url]

Exercises all three citizen flows plus the officer dashboard and prints a
pass/fail report. Exits non-zero if anything fails.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results: list[tuple[bool, str, str]] = []


def request(path: str, payload: dict | None = None, method: str = "GET") -> tuple[int, dict]:
    url = f"{BASE}{path}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"raw": body}


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((condition, name, detail))
    marker = PASS if condition else FAIL
    print(f"  [{marker}] {name}" + (f"  -> {detail}" if detail else ""))


def chat(text: str, session: str | None = None, speak: bool = False) -> dict:
    payload = {"text": text, "speak": speak}
    if session:
        payload["sessionId"] = session
    _, body = request("/api/chat/text", payload, "POST")
    return body.get("data", body)


def main() -> int:
    print(f"\nJanVaani UP smoke test -> {BASE}\n")

    # --- health -----------------------------------------------------------
    print("health")
    status, body = request("/api/health")
    check("GET /api/health returns 200", status == 200, f"status={status}")
    health = body.get("data", body)
    check("service is janvaani-up", health.get("service") == "janvaani-up")
    check("database seeded", health.get("database", {}).get("seeded") is True)
    check("scheme corpus loaded", health.get("vector", {}).get("schemes", 0) >= 8,
          f"schemes={health.get('vector', {}).get('schemes')}")
    print(f"      mode={health.get('mode')} llm={health.get('llm', {}).get('available')} "
          f"asr={health.get('asr', {}).get('available')} tts={health.get('tts', {}).get('edgeTtsAvailable')}")

    # --- flow 1: scheme eligibility --------------------------------------
    print("\nflow 1 - scheme eligibility (Bhojpuri)")
    result = chat("Hamre paas 2 bigha zameen ba, kaun sarkari yojana mili?")
    intent = result.get("intent", {})
    check("intent is scheme_eligibility", intent.get("name") == "scheme_eligibility",
          f"got={intent.get('name')}")
    check("land holding extracted", intent.get("entities", {}).get("landBigha") == 2,
          f"landBigha={intent.get('entities', {}).get('landBigha')}")
    check("reply is non-empty", bool(result.get("reply", {}).get("text")))
    check("citations returned", len(result.get("citations", [])) > 0,
          f"n={len(result.get('citations', []))}")
    if result.get("citations"):
        print(f"      cite: {result['citations'][0]['citation']} | {result['citations'][0]['source']}")

    # --- flow 1b: scheme documents ---------------------------------------
    print("\nflow 1b - required documents")
    result = chat("PM Awas ke liye kaun kaun se document chahiye?")
    check("intent is scheme_documents", result.get("intent", {}).get("name") == "scheme_documents",
          f"got={result.get('intent', {}).get('name')}")
    check("document card produced", any(c.get("type") == "documents" for c in result.get("cards", [])))

    # --- flow 2: grievance ------------------------------------------------
    print("\nflow 2 - conversational grievance (multi-turn)")
    session = None
    result = chat("Hamare gaon ke transformer 4 din se jala pada hai, koi sun nahi raha.", session)
    session = result.get("sessionId")
    intent = result.get("intent", {})
    check("intent is grievance_file", intent.get("name") == "grievance_file",
          f"got={intent.get('name')}")
    check("category is electricity", intent.get("entities", {}).get("category") == "electricity",
          f"got={intent.get('entities', {}).get('category')}")
    check("duration extracted", intent.get("entities", {}).get("durationDays") == 4,
          f"got={intent.get('entities', {}).get('durationDays')}")
    check("asks for a missing slot", bool(result.get("awaiting")), f"awaiting={result.get('awaiting')}")

    result = chat("Barabanki", session)
    session = result.get("sessionId")
    check("still collecting slots", bool(result.get("awaiting")), f"awaiting={result.get('awaiting')}")

    result = chat("Tanda block, Bansipur gaon", session)
    session = result.get("sessionId")

    result = chat("9876543210", session)
    session = result.get("sessionId")
    tickets = result.get("tickets", [])
    check("ticket created", len(tickets) == 1, f"n={len(tickets)}")
    if tickets:
        ticket = tickets[0]
        check("ticket id format", ticket.get("id", "").startswith("JVUP-"), f"id={ticket.get('id')}")
        check("ticket has district", bool(ticket.get("district")), f"district={ticket.get('district')}")
        check("ticket has village", bool(ticket.get("village")), f"village={ticket.get('village')}")
        check("ticket contact masked", "9876543210" not in json.dumps(ticket, ensure_ascii=False),
              f"contact={ticket.get('contact')}")
        check("ticket has hindi summary", len(ticket.get("summary") or "") > 20)

    # --- flow 3: status tracker ------------------------------------------
    print("\nflow 3 - application status tracker")
    result = chat("Mera ration card ya PM Kisan ka paisa kahan tak pahuncha?")
    check("intent is status_track", result.get("intent", {}).get("name") == "status_track",
          f"got={result.get('intent', {}).get('name')}")
    check("asks for identifier", bool(result.get("awaiting")), f"awaiting={result.get('awaiting')}")

    status, body = request("/api/applications/lookup?aadhaarLast4=4821")
    data = body.get("data", body)
    check("lookup by aadhaar last4 works", data.get("found") is True)
    check("applications returned", len(data.get("applications", [])) >= 2,
          f"n={len(data.get('applications', []))}")
    if data.get("applications"):
        citizen_aadhaar = data.get("citizen", {}).get("aadhaar", "")
        check("aadhaar masked in payload", citizen_aadhaar.startswith("XXXX-XXXX-"),
              f"aadhaar={citizen_aadhaar}")
        print(f"      apps: {', '.join(a.get('shortName', '') for a in data['applications'])}")

    status, body = request("/api/applications/lookup?mobile=9876543210")
    data = body.get("data", body)
    check("lookup by mobile works", data.get("found") is True)

    status, body = request("/api/applications/lookup?aadhaarLast4=0000")
    data = body.get("data", body)
    check("unknown identifier returns found=false", data.get("found") is False)

    # --- officer dashboard ------------------------------------------------
    print("\nofficer dashboard")
    status, body = request("/api/admin/stats")
    stats = body.get("data", {}).get("stats", {})
    check("stats endpoint works", status == 200)
    check("totals present", stats.get("totals", {}).get("tickets", 0) > 0,
          f"tickets={stats.get('totals', {}).get('tickets')}")
    check("category breakdown present", len(stats.get("byCategory", [])) > 0)
    check("timeline has 14 points", len(stats.get("timeline", [])) == 14,
          f"n={len(stats.get('timeline', []))}")
    check("live feed present", len(body.get("data", {}).get("feed", [])) > 0)

    status, body = request("/api/tickets")
    tickets = body.get("data", {}).get("tickets", [])
    check("tickets endpoint works", status == 200 and len(tickets) > 0, f"n={len(tickets)}")

    if tickets:
        ticket_id = tickets[0]["id"]
        status, body = request(f"/api/tickets/{ticket_id}", {"status": "IN_PROGRESS"}, "PATCH")
        check("ticket status update works", status == 200, f"status={status}")
        check("status persisted", body.get("data", {}).get("ticket", {}).get("status") == "IN_PROGRESS")

    # --- schemes catalogue -------------------------------------------------
    print("\nscheme catalogue")
    status, body = request("/api/schemes")
    schemes = body.get("data", {}).get("schemes", [])
    check("scheme list works", status == 200 and len(schemes) >= 8, f"n={len(schemes)}")
    status, body = request("/api/schemes/pm-kisan")
    check("scheme detail works", status == 200)

    status, body = request("/api/schemes/search", {"query": "2 bigha zameen kisan"}, "POST")
    data = body.get("data", body)
    check("grounded search works", status == 200 and bool(data.get("answer")))
    check("search returns citations", len(data.get("citations", [])) > 0)

    # --- whatsapp stub -----------------------------------------------------
    print("\nwhatsapp stub")
    status, body = request("/api/whatsapp/webhook",
                           {"entry": [{"changes": [{"value": {"messages": [
                               {"from": "919876543210", "text": {"body": "paani nahi aa raha"}}]}}]}]}, "POST")
    check("webhook accepts a message", status == 200, f"status={status}")
    check("webhook produced a reply", len(body.get("data", {}).get("replies", [])) > 0)

    # --- summary -----------------------------------------------------------
    failed = [r for r in results if not r[0]]
    print(f"\n{'=' * 62}")
    print(f"  {len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("  failures:")
        for _, name, detail in failed:
            print(f"    - {name}  {detail}")
    print(f"{'=' * 62}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
