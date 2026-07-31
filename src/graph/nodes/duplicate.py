"""
Duplicate check node - two-stage duplicate detection
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import ValidationError

from src.graph.state import BugTriageState
from src.models.triage import DuplicateComparison
from src.services.llm_service import llm_service
from src.services.embedding_service import embedding_service
from src.services.gitea_service import gitea_service
from src.config import settings
from src.utils.logging import logger


def find_by_stacktrace_hash(stacktrace_hash: str) -> Optional[dict[str, Any]]:
    """Find existing issue with matching stacktrace hash in body metadata."""
    try:
        issues = gitea_service.list_issues_sync(state="open", limit=100)
    except Exception as exc:
        logger.warning("stacktrace_hash_lookup_failed", error=str(exc))
        return None

    marker = f"stacktrace_hash:{stacktrace_hash}"
    for issue in issues:
        body = issue.get("body") or ""
        if marker in body or stacktrace_hash in body:
            return {
                "id": issue["number"],
                "title": issue.get("title", ""),
                "description": body,
                "score": 1.0,
            }
    return None


def get_duplicate_candidates(
    report: str,
    threshold: float | None = None,
) -> list[dict[str, Any]]:
    """Retrieve top-K similar issues via embedding similarity.

    Uses top-K recall (not hard threshold) so LLM verification can catch
    paraphrased duplicates that score below the embedding cutoff (e.g. B5 vs EXIST-1).
    """
    recall_floor = threshold or settings.embedding_threshold

    try:
        issues = gitea_service.list_issues_sync(state="open", limit=100)
    except Exception as exc:
        logger.warning("duplicate_candidate_fetch_failed", error=str(exc))
        return []

    if not issues:
        return []

    query_embedding = embedding_service.generate_embedding(report[:4000])
    candidates: list[dict[str, Any]] = []

    for issue in issues:
        text = f"{issue.get('title', '')} {issue.get('body', '')}"[:4000]
        if not text.strip():
            continue
        issue_embedding = embedding_service.generate_embedding(text)
        score = embedding_service.cosine_similarity(query_embedding, issue_embedding)
        candidates.append({
            "id": issue["number"],
            "title": issue.get("title", ""),
            "description": issue.get("body", ""),
            "score": score,
        })

    candidates.sort(key=lambda item: item["score"], reverse=True)
    top_k = candidates[:5]

    if not top_k:
        return []

    if top_k[0]["score"] < recall_floor:
        logger.info(
            "duplicate_candidates_below_recall_floor",
            top_score=top_k[0]["score"],
            recall_floor=recall_floor,
            returning=len(top_k),
        )

    return top_k


def duplicate_check_node(state: BugTriageState) -> dict:
    """Two-stage duplicate detection: hash fast-path, then embedding + LLM."""
    start = datetime.now()

    logger.info(
        "node_start",
        node="duplicate_check",
        thread_id=state.get("thread_id"),
    )

    if state.get("stacktrace_hash"):
        existing = find_by_stacktrace_hash(state["stacktrace_hash"])
        if existing:
            duration_ms = (datetime.now() - start).total_seconds() * 1000
            return {
                "is_duplicate": True,
                "duplicate_issue_id": existing["id"],
                "duplicate_confidence": 1.0,
                "duplicate_candidates": [existing],
                "node_timings": [{"node": "duplicate_check", "duration_ms": duration_ms}],
            }

    candidates = get_duplicate_candidates(state["cleaned_report"])

    if not candidates:
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        return {
            "is_duplicate": False,
            "duplicate_candidates": [],
            "duplicate_confidence": 0.0,
            "node_timings": [{"node": "duplicate_check", "duration_ms": duration_ms}],
        }

    confirmed: list[tuple[int, float, dict]] = []

    for candidate in candidates[:3]:
        prompt = f"""Are these bug reports duplicates?

New report:
Title: {state.get("title", "N/A")}
Description: {state["cleaned_report"]}

Existing issue #{candidate["id"]}:
Title: {candidate["title"]}
Description: {candidate["description"]}

Return:
- is_duplicate: true if they describe the SAME bug (not just related)
- confidence: 0.0-1.0
- reasoning: brief explanation"""

        try:
            result = llm_service.invoke_fast(prompt, DuplicateComparison)
        except ValidationError as exc:
            logger.warning(
                "duplicate_comparison_validation_failed",
                candidate_id=candidate["id"],
                error=str(exc),
            )
            continue
        except Exception as exc:
            logger.warning(
                "duplicate_comparison_failed",
                candidate_id=candidate["id"],
                error=str(exc),
            )
            continue

        if result.is_duplicate and result.confidence > settings.duplicate_confidence_threshold:
            confirmed.append((candidate["id"], result.confidence, candidate))

    if confirmed:
        duplicate_id, dup_confidence, _ = min(confirmed, key=lambda item: item[0])
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        return {
            "is_duplicate": True,
            "duplicate_issue_id": duplicate_id,
            "duplicate_confidence": dup_confidence,
            "duplicate_candidates": candidates,
            "classification_history": [{
                "action": "duplicate_detected",
                "confidence": dup_confidence,
                "reasoning": f"Linked to earliest matching open issue #{duplicate_id}",
            }],
            "node_timings": [{"node": "duplicate_check", "duration_ms": duration_ms}],
        }

    max_score = max(c.get("score", 0.0) for c in candidates)
    duration_ms = (datetime.now() - start).total_seconds() * 1000

    logger.info(
        "node_complete",
        node="duplicate_check",
        thread_id=state.get("thread_id"),
        is_duplicate=False,
        candidates=len(candidates),
        duration_ms=duration_ms,
    )

    return {
        "is_duplicate": False,
        "duplicate_candidates": candidates,
        "duplicate_confidence": max_score,
        "node_timings": [{"node": "duplicate_check", "duration_ms": duration_ms}],
    }
