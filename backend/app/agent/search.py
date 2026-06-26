import json
import re
import unicodedata

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.faults import maybe_raise_agent_fault
from app.authz import is_manager
from app.enums import UserRole
from app.models import Customer, User


def build_fts5_phrase_query(raw_query: str) -> str | None:
    normalized = unicodedata.normalize("NFC", raw_query.replace("\r", " "))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if normalized == "":
        return None
    tokens = normalized.split(" ")
    escaped_tokens = [f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens]
    return " ".join(escaped_tokens)


def search_knowledge_base(
    db: Session,
    *,
    query: str,
    current_user: User,
    customer_id: int,
    source_types: list[str],
    limit: int,
    max_bm25_rank: float | None,
) -> list[dict[str, object]]:
    fts_query = build_fts5_phrase_query(query)
    if fts_query is None or not source_types:
        return []
    maybe_raise_agent_fault("fts5_match_syntax_error_hook")

    customer = db.get(Customer, customer_id)
    customer_access_allowed = bool(
        customer is not None and (is_manager(current_user) or customer.owner_id == current_user.id)
    )
    role = current_user.role.value
    user_id = current_user.id
    team_scope_json = json.dumps([], ensure_ascii=False)
    source_types_json = json.dumps(source_types, ensure_ascii=False)
    params = {
        "fts_query": fts_query,
        "source_types_json": source_types_json,
        "team_scope_json": team_scope_json,
        "role": role,
        "user_id": user_id,
        "customer_id": customer_id,
        "customer_access_allowed": 1 if customer_access_allowed else 0,
        "max_bm25_rank": max_bm25_rank,
        "limit": limit,
    }
    rows = db.execute(
        text(
            """
            WITH ranked AS (
              SELECT
                kc.id AS chunk_id,
                kc.doc_id AS doc_id,
                kd.title AS title,
                kd.source_type AS source_type,
                kc.text AS text,
                kd.checksum AS doc_checksum,
                kd.doc_version AS doc_version,
                bm25(knowledge_chunks_fts) AS rank
              FROM knowledge_chunks_fts
              JOIN knowledge_chunks AS kc ON kc.id = knowledge_chunks_fts.chunk_id
              JOIN knowledge_docs AS kd ON kd.id = kc.doc_id
              WHERE knowledge_chunks_fts MATCH :fts_query
                AND EXISTS (
                  SELECT 1 FROM json_each(:source_types_json) AS st
                  WHERE st.value = kd.source_type
                )
                AND (
                  (kd.visibility = 'all_sales' AND :role IN ('sales', 'manager'))
                  OR (kd.visibility = 'managers_only' AND :role = 'manager')
                  OR (
                    kd.visibility = 'owner_team'
                    AND EXISTS (
                      SELECT 1 FROM json_each(:team_scope_json) AS ts
                      WHERE ts.value = kd.team_id
                    )
                  )
                  OR (
                    kd.visibility = 'customer_scoped'
                    AND kd.customer_id = :customer_id
                    AND :customer_access_allowed = 1
                  )
                  OR (
                    kd.visibility = 'private'
                    AND (
                      kd.owner_user_id = :user_id
                      OR EXISTS (
                        SELECT 1
                        FROM json_each(COALESCE(kd.allowed_user_ids_json, '[]')) AS au
                        WHERE au.value = :user_id
                      )
                    )
                  )
                )
                AND (
                  kd.allowed_roles_json IS NULL
                  OR json_array_length(kd.allowed_roles_json) = 0
                  OR EXISTS (
                    SELECT 1 FROM json_each(kd.allowed_roles_json) AS ar
                    WHERE ar.value = :role
                  )
                )
            )
            SELECT * FROM ranked
            WHERE (:max_bm25_rank IS NULL OR rank <= :max_bm25_rank)
            ORDER BY rank ASC
            LIMIT :limit
            """
        ),
        params,
    ).mappings()
    return [
        {
            "chunk_id": row["chunk_id"],
            "doc_id": row["doc_id"],
            "title": row["title"],
            "source_type": row["source_type"],
            "text": row["text"],
            "doc_checksum": row["doc_checksum"],
            "doc_version": row["doc_version"],
            "rank": row["rank"],
        }
        for row in rows
    ]


def default_source_types_for_role(role: UserRole) -> list[str]:
    return ["sales_playbook", "case_note", "product_note"] if role == UserRole.sales else [
        "sales_playbook",
        "case_note",
        "product_note",
        "manager_note",
    ]
