"""RAG retrieval tests - the knowledge base must actually recall the right scheme."""

from __future__ import annotations

from app.services import rag


def test_corpus_loads():
    schemes = rag.load_schemes()
    assert len(schemes) >= 8
    ids = {scheme["id"] for scheme in schemes}
    assert {"pm-kisan", "pm-awas-gramin", "nfsa-ration", "mpy-pension"} <= ids


def test_every_scheme_has_sections_with_criteria():
    for scheme in rag.load_schemes():
        assert scheme["sections"], f"{scheme['id']} has no sections"
        for section in scheme["sections"]:
            assert section["body"], f"{scheme['id']}/{section['id']} has no body"
            assert section["source"], f"{scheme['id']}/{section['id']} has no source"


def test_bhojpuri_land_query_recalls_pm_kisan():
    results = rag.get_retriever().search("hamare paas 2 bigha zameen hai kaun yojana milegi", top_k=3)
    assert results, "nothing retrieved"
    assert results[0][0].scheme_id == "pm-kisan"


def test_electricity_query_recalls_electricity_content():
    results = rag.get_retriever().search("bijli transformer jala pada hai", top_k=3)
    assert results
    # The complaint terms map onto the right domain even without a scheme keyword.
    text = " ".join(chunk.searchable_text().lower() for chunk, _ in results)
    assert any(token in text for token in ("electricity", "bijli", "land"))


def test_ration_card_query_recalls_nfsa():
    results = rag.get_retriever().search("mera ration card ka kya haal hai", top_k=3)
    assert results
    assert results[0][0].scheme_id == "nfsa-ration"


def test_pension_query_recalls_pension():
    results = rag.get_retriever().search("widow pension kitne milega", top_k=3)
    assert results
    assert results[0][0].scheme_id == "mpy-pension"


def test_kanya_sumangala_query():
    results = rag.get_retriever().search("ladki ki kanya sumangala yojana kitne paisa", top_k=3)
    assert results
    assert results[0][0].scheme_id == "kanya-sumangala"


def test_scheme_filter_restricts_results():
    results = rag.get_retriever().search("zameen bigha", top_k=5, scheme_filter="pm-kisan")
    assert results
    assert all(chunk.scheme_id == "pm-kisan" for chunk, _ in results)


def test_empty_query_returns_nothing():
    assert rag.get_retriever().search("   ", top_k=3) == []


def test_citations_are_well_formed():
    chunks = [chunk for chunk, _ in rag.get_retriever().search("kisan bigha zameen", top_k=2)]
    citations = rag.build_citations(chunks, limit=2)
    assert len(citations) == 2
    for citation in citations:
        payload = citation.to_dict()
        assert payload["schemeId"]
        assert payload["sectionId"]
        assert payload["source"]
        assert "§" in payload["citation"]


def test_tokenizer_keeps_devanagari():
    tokens = rag.tokenize("हमारे पास 2 बीघा जमीन है")
    assert "हमारे" in tokens
    assert "2" in tokens


def test_light_stem_does_not_destroy_short_tokens():
    assert rag.light_stem("aad") == "aad"
    assert len(rag.light_stem("yojana")) >= 3


def test_eligibility_question_ranks_the_criteria_section_first():
    """A citizen asking "am I eligible?" must not get the exclusions paragraph."""
    ranked = rag.get_retriever().search("kaun sa yojana milegi mujhe", top_k=4)
    reranked = rag.rerank_by_intent("kaun sa yojana milegi mujhe", ranked, "scheme_eligibility")
    assert reranked
    assert reranked[0][0].section_id.endswith("eligibility")


def test_rerank_is_stable_for_queries_without_an_intent():
    ranked = rag.get_retriever().search("kisan bigha zameen", top_k=3)
    reranked = rag.rerank_by_intent("kisan bigha zameen", ranked, None)
    assert [chunk.chunk_id for chunk, _ in reranked] == [chunk.chunk_id for chunk, _ in ranked]


def test_rerank_handles_an_empty_result_set():
    assert rag.rerank_by_intent("anything", [], "scheme_eligibility") == []


def test_section_affinity_prefers_the_matching_section_type():
    chunks = {chunk.section_id.split(".")[-1]: chunk for chunk in rag.get_retriever().chunks}
    assert rag.section_affinity("kaun si yojana milegi", chunks["eligibility"], "scheme_eligibility") > 0
    assert rag.section_affinity("kaun si yojana milegi", chunks["interest"], "scheme_eligibility") == 0
