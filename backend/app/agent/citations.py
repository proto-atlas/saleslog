from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.agent.text import normalize_text, sha256_text
from app.authz import get_customer_authorized, is_manager
from app.enums import KnowledgeVisibility
from app.models import AgentRun, AgentRunSource, KnowledgeDoc, User, Visit, utcnow_naive
from app.sqlalchemy_result import result_rowcount

SOURCE_EXCERPT_RETENTION_DAYS = 30
CITATION_QUOTE_KEY = "quoted_text"


def create_run_source(
    db: Session,
    *,
    run_id: int,
    source_type: str,
    source_id: str,
    source_version: str,
    label: str,
    body: str,
    chunk_id: str | None = None,
) -> AgentRunSource:
    normalized_body = normalize_text(body)
    source = AgentRunSource(
        run_id=run_id,
        source_type=source_type,
        source_id=source_id,
        source_version=source_version,
        source_checksum=sha256_text(normalized_body),
        chunk_id=chunk_id,
        label=label,
        char_start=0,
        char_end=len(normalized_body),
        source_excerpt=normalized_body,
        source_excerpt_hash=sha256_text(normalized_body),
        expires_at=utcnow_naive() + timedelta(days=SOURCE_EXCERPT_RETENTION_DAYS),
    )
    db.add(source)
    db.flush()
    return source


def enrich_citations_on_server(
    db: Session,
    *,
    run_id: int,
    current_user: User,
    customer_id: int,
    citation_candidates: list[dict[str, object]],
) -> list[dict[str, object]]:
    citations: list[dict[str, object]] = []
    for index, candidate in enumerate(citation_candidates, start=1):
        source_type = str(candidate.get("source_type", ""))
        source_id = str(candidate.get("source_id", ""))
        chunk_id_value = candidate.get("chunk_id")
        chunk_id = str(chunk_id_value) if chunk_id_value is not None else None
        quoted_text = str(candidate.get("quoted_text", ""))
        source = db.scalar(
            select(AgentRunSource).where(
                AgentRunSource.run_id == run_id,
                AgentRunSource.source_type == source_type,
                AgentRunSource.source_id == source_id,
                AgentRunSource.chunk_id == chunk_id,
            )
        )
        if source is None or source.source_excerpt is None:
            continue
        if not source_still_authorized(
            db,
            source=source,
            current_user=current_user,
            customer_id=customer_id,
        ):
            continue
        expected_checksum = candidate.get("source_checksum")
        if isinstance(expected_checksum, str) and expected_checksum != source.source_checksum:
            continue
        normalized_body = normalize_text(source.source_excerpt)
        normalized_quote = normalize_text(quoted_text)
        start = normalized_body.find(normalized_quote)
        if start < 0:
            continue
        end = start + len(normalized_quote)
        citations.append(
            {
                "citation_id": f"cit_{index:03d}",
                "claim_id": candidate.get("claim_id"),
                "source_type": source.source_type,
                "source_id": source.source_id,
                "source_version": source.source_version,
                "source_checksum": source.source_checksum,
                "chunk_id": source.chunk_id,
                "char_start": start,
                "char_end": end,
                "offset_unit": source.offset_unit,
                "excerpt_hash": sha256_text(normalized_quote),
                "label": source.label,
                "agent_run_source_id": source.id,
            }
        )
    return citations


def redact_expired_run_sources(db: Session) -> int:
    now = utcnow_naive()
    result = db.execute(
        update(AgentRunSource)
        .where(
            AgentRunSource.expires_at.is_not(None),
            AgentRunSource.expires_at < now,
            AgentRunSource.source_excerpt.is_not(None),
        )
        .values(source_excerpt=None, source_excerpt_redacted_at=now)
    )
    return result_rowcount(result)


def redact_citation_candidate_quotes(
    candidates: list[dict[str, object]],
) -> list[dict[str, object]]:
    return [
        {key: value for key, value in candidate.items() if key != CITATION_QUOTE_KEY}
        for candidate in candidates
    ]


def redact_artifact_content_citation_quotes(
    content: dict[str, object],
) -> dict[str, object]:
    redacted = dict(content)
    candidates = redacted.get("citation_candidates")
    if isinstance(candidates, list):
        redacted["citation_candidates"] = [
            {
                str(key): value
                for key, value in candidate.items()
                if isinstance(key, str) and key != CITATION_QUOTE_KEY
            }
            for candidate in candidates
            if isinstance(candidate, dict)
        ]
    return redacted


def source_still_authorized(
    db: Session,
    *,
    source: AgentRunSource,
    current_user: User,
    customer_id: int,
) -> bool:
    if source.source_type == "customer":
        try:
            get_customer_authorized(db, current_user, int(source.source_id))
        except Exception:
            return False
        return True
    if source.source_type == "activity":
        return _visit_still_authorized(db, source=source, current_user=current_user)
    return _knowledge_doc_still_authorized(
        db,
        source=source,
        current_user=current_user,
        customer_id=customer_id,
    )


def run_sources_all_authorized(
    db: Session, *, run: AgentRun, current_user: User
) -> bool:
    sources = db.scalars(
        select(AgentRunSource)
        .where(AgentRunSource.run_id == run.id)
        .order_by(AgentRunSource.id)
    ).all()
    return all(
        source_still_authorized(
            db,
            source=source,
            current_user=current_user,
            customer_id=run.customer_id,
        )
        for source in sources
    )


def _visit_still_authorized(
    db: Session, *, source: AgentRunSource, current_user: User
) -> bool:
    try:
        visit_id = int(source.source_id)
    except ValueError:
        return False
    visit = db.get(Visit, visit_id)
    if visit is None:
        return False
    return is_manager(current_user) or visit.user_id == current_user.id


def _knowledge_doc_still_authorized(
    db: Session,
    *,
    source: AgentRunSource,
    current_user: User,
    customer_id: int,
) -> bool:
    try:
        doc_id = int(source.source_id)
    except ValueError:
        return False
    doc = db.get(KnowledgeDoc, doc_id)
    if doc is None or doc.source_type != source.source_type:
        return False
    if doc.allowed_roles_json and current_user.role.value not in doc.allowed_roles_json:
        return False
    if doc.visibility == KnowledgeVisibility.all_sales:
        return current_user.role.value in ("sales", "manager")
    if doc.visibility == KnowledgeVisibility.managers_only:
        return is_manager(current_user)
    if doc.visibility == KnowledgeVisibility.customer_scoped:
        if doc.customer_id != customer_id:
            return False
        try:
            get_customer_authorized(db, current_user, customer_id)
        except Exception:
            return False
        return True
    if doc.visibility == KnowledgeVisibility.private:
        return (
            doc.owner_user_id == current_user.id
            or current_user.id in (doc.allowed_user_ids_json or [])
        )
    return False


def validate_claim_citations(
    *,
    claims: list[dict[str, object]],
    citations: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    citations_by_claim: dict[str, list[dict[str, object]]] = {}
    for citation in citations:
        claim_id = str(citation.get("claim_id", ""))
        citations_by_claim.setdefault(claim_id, []).append(citation)

    valid_claims: list[dict[str, object]] = []
    uncertainties: list[dict[str, object]] = []
    for claim in claims:
        claim_id = str(claim.get("claim_id", ""))
        requires_citation = bool(claim.get("requires_citation", False))
        claim_citations = citations_by_claim.get(claim_id, [])
        if requires_citation and not claim_citations:
            uncertainties.append(
                {
                    "claim_id": claim_id,
                    "message_key": "citation_missing",
                    "text": claim.get("text", ""),
                }
            )
            continue
        claim["citation_ids"] = [citation["citation_id"] for citation in claim_citations]
        valid_claims.append(claim)
    return valid_claims, uncertainties
