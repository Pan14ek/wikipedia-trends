"""Deterministic semantic normalization and hard topic relevance gates."""

from __future__ import annotations

from wiki_trends.article_resolver import _PageLookup, _SemanticMetadata, _topic_candidate_evidence, normalize_topic_text
from wiki_trends.models import TopicCandidateDecision


def _page(title: str, wikidata_id: str | None = "Q1") -> _PageLookup:
    return _PageLookup(
        title=title,
        page_id=1,
        url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
        wikidata_id=wikidata_id,
        language_links={},
        is_disambiguation=False,
    )


def test_topic_text_normalization_handles_nfkc_case_punctuation_and_whitespace() -> None:
    assert normalize_topic_text("  Ｌｅａｒｎｉｎｇ__ENGLISH—Now! ") == "learning english now"


def test_exact_title_match_is_a_direct_semantic_match() -> None:
    evidence = _topic_candidate_evidence("Astronomy", _page("ASTRONOMY"), 5, _SemanticMetadata(None, (), (), (), "Q1"))

    assert evidence.exact_title_match is True
    assert evidence.decision is TopicCandidateDecision.ACCEPTED
    assert evidence.reason == "exact_title_match"


def test_exact_label_match_and_exact_alias_match_are_accepted() -> None:
    label = _topic_candidate_evidence(
        "Space science", _page("Astronomy"), 2, _SemanticMetadata("Space science", (), (), ("en",), "Q1")
    )
    alias = _topic_candidate_evidence(
        "Star study", _page("Astronomy"), 2, _SemanticMetadata("Astronomy", ("Star study",), (), ("en",), "Q1")
    )

    assert label.exact_label_match is True and label.decision is TopicCandidateDecision.ACCEPTED
    assert alias.exact_alias_match is True and alias.decision is TopicCandidateDecision.ACCEPTED


def test_token_coverage_requires_threshold_and_lexical_anchor() -> None:
    covered = _topic_candidate_evidence(
        "learning English",
        _page("English language"),
        4,
        _SemanticMetadata("English language", (), ("learning English for study",), ("en",), "Q1"),
    )
    description_only = _topic_candidate_evidence(
        "learning English",
        _page("Language education"),
        1,
        _SemanticMetadata("Language education", (), ("learning English for study",), ("en",), "Q1"),
    )

    assert covered.query_token_coverage == 1.0
    assert covered.lexical_anchor is True
    assert covered.decision is TopicCandidateDecision.ACCEPTED
    assert description_only.query_token_coverage == 1.0
    assert description_only.lexical_anchor is False
    assert description_only.decision is TopicCandidateDecision.REJECTED


def test_rank_one_and_one_shared_token_cannot_pass_relevance_gate() -> None:
    evidence = _topic_candidate_evidence(
        "intermittent fasting",
        _page("Fasting"),
        1,
        _SemanticMetadata("Fasting", (), ("abstaining from food for health",), ("en",), "Q1"),
    )

    assert evidence.search_rank == 1
    assert evidence.query_token_coverage == 0.5
    assert evidence.lexical_anchor is True
    assert evidence.decision is TopicCandidateDecision.REJECTED
    assert evidence.reason == "insufficient_semantic_evidence"
