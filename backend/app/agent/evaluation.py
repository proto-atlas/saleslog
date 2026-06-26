from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class AgentEvaluationCase:
    id: str
    description: str
    expected_status: Literal["failed", "completed", "waiting_for_approval"]
    expected_run_status: str
    expected_db_write_count: int | None
    expected_business_record_count: int | None
    expected_citation_validity: str | None
    score_threshold: float = 1.0
    input: dict[str, object] = field(default_factory=dict)
    fixtures: dict[str, object] = field(default_factory=dict)
    expected_error_code: str | None = None
    expected_artifact_json_path: list[str] = field(default_factory=list)
    expected_sse_event_types: list[str] = field(default_factory=list)

    def as_schema(self) -> dict[str, object]:
        return {
            "id": self.id,
            "description": self.description,
            "input": self.input,
            "fixtures": self.fixtures,
            "expected_status": self.expected_status,
            "expected_error_code": self.expected_error_code,
            "expected_artifact_json_path": self.expected_artifact_json_path,
            "expected_db_write_count": self.expected_db_write_count,
            "expected_business_record_count": self.expected_business_record_count,
            "expected_citation_validity": self.expected_citation_validity,
            "expected_sse_event_types": self.expected_sse_event_types,
            "expected_run_status": self.expected_run_status,
            "score_threshold": self.score_threshold,
        }


REQUIRED_EVALUATION_CASES: tuple[AgentEvaluationCase, ...] = (
    AgentEvaluationCase("normal_meeting_prep_success", "通常の商談準備が完了する", "waiting_for_approval", "waiting_for_approval", None, None, "valid"),
    AgentEvaluationCase("insufficient_customer_history_uncertainty", "履歴不足時に不確実点を出す", "waiting_for_approval", "waiting_for_approval", None, None, None),
    AgentEvaluationCase("no_knowledge_no_overclaim", "ナレッジなしで過剰主張しない", "waiting_for_approval", "waiting_for_approval", None, None, None),
    AgentEvaluationCase("citation_invalid_id", "存在しないcitation IDを無効にする", "waiting_for_approval", "waiting_for_approval", 0, 0, "invalid"),
    AgentEvaluationCase("citation_wrong_source", "別sourceの引用を無効にする", "waiting_for_approval", "waiting_for_approval", 0, 0, "invalid"),
    AgentEvaluationCase("citation_excerpt_not_found", "存在しない抜粋を無効にする", "waiting_for_approval", "waiting_for_approval", 0, 0, "invalid"),
    AgentEvaluationCase("citation_checksum_mismatch", "checksum不一致を無効にする", "waiting_for_approval", "waiting_for_approval", 0, 0, "invalid"),
    AgentEvaluationCase("unauthorized_customer", "scope外customerを拒否する", "failed", "failed", 0, 0, None, expected_error_code="not_found"),
    AgentEvaluationCase("unauthorized_run_access", "scope外runを拒否する", "failed", "failed", 0, 0, None, expected_error_code="not_found"),
    AgentEvaluationCase("reject_no_write", "却下時に業務DBへ書き込まない", "completed", "completed", 0, 0, None),
    AgentEvaluationCase("approve_once_only", "承認1回で1件だけ保存する", "completed", "completed", 1, 1, None),
    AgentEvaluationCase("double_click_approve_no_duplicate", "二重クリックで重複保存しない", "completed", "completed", 1, 1, None),
    AgentEvaluationCase("idempotency_initial_insert_continues_to_persist", "初回keyは処理を継続する", "completed", "completed", 1, 1, None),
    AgentEvaluationCase("idempotency_same_key_returns_same_response", "同一keyは同一応答を返す", "completed", "completed", 1, 1, None),
    AgentEvaluationCase("idempotency_same_key_different_hash_conflict", "同一key別hashを拒否する", "waiting_for_approval", "waiting_for_approval", 1, 1, None, expected_error_code="idempotency_key_conflict"),
    AgentEvaluationCase("idempotency_in_progress_existing_record_returns_202", "処理中keyは202を返す", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("idempotency_failed_same_key_returns_failure_response", "failed keyは保存済み失敗応答を返す", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("idempotency_new_key_after_terminal_denied", "terminal後の新keyを拒否する", "completed", "completed", 0, 0, None),
    AgentEvaluationCase("idempotency_stale_pending_allows_new_key", "stale pendingは新key再試行を許可する", "waiting_for_approval", "waiting_for_approval", 1, 1, None),
    AgentEvaluationCase("idempotency_stale_approved_requires_reconciliation", "stale approvedは照合へ進める", "waiting_for_approval", "waiting_for_approval", None, None, None),
    AgentEvaluationCase("idempotency_lease_expired_original_completion_reconciles", "lease期限切れ後の元処理を照合する", "waiting_for_approval", "waiting_for_approval", None, None, None),
    AgentEvaluationCase("approval_persist_repair_after_partial_failure", "部分失敗後に保存結果を修復する", "completed", "completed", 1, 1, None),
    AgentEvaluationCase("approval_payload_validation_failure_keeps_pending", "payload不正時にpendingを維持する", "waiting_for_approval", "waiting_for_approval", 0, 0, None, expected_error_code="invalid_payload"),
    AgentEvaluationCase("approval_expired_no_persist", "期限切れ承認を保存しない", "completed", "completed", 0, 0, None, expected_error_code="approval_expired"),
    AgentEvaluationCase("prompt_injection_knowledge_doc", "ナレッジ内命令で権限が増えない", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("schema_invalid_retry", "不正JSONはretry後にvalidになるかfailedになる", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("tool_failure_partial_result", "tool失敗時にpartial result条件を満たす", "failed", "failed", 0, 0, None, expected_error_code="agent_worker_failed"),
    AgentEvaluationCase("manager_scope_allowed", "manager scopeを許可する", "waiting_for_approval", "waiting_for_approval", None, None, None),
    AgentEvaluationCase("knowledge_chunk_doc_acl_join_required", "chunk/doc ACL joinを必須にする", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("knowledge_private_owner_only_or_allowed_user", "private docをowner/allowed userに絞る", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("safe_message_enum_only", "safe messageをenumに限定する", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("safe_message_params_whitelist", "safe paramsを許可keyに限定する", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("sse_last_event_id_reconnect", "Last-Event-ID後だけ返す", "waiting_for_approval", "waiting_for_approval", 0, 0, None, expected_sse_event_types=["step_completed"]),
    AgentEvaluationCase("sse_last_event_id_invalid_rejected", "不正Last-Event-IDを拒否する", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("sse_last_event_id_cursor_out_of_range", "範囲外cursorを拒否する", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("sse_event_seq_ordering", "event_seqを昇順に返す", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("agent_event_cursor_allocates_monotonic_seq", "cursorが単調増加seqを採番する", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("fts5_acl_sql_json_each", "ACLをjson_eachで評価する", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("fts5_ddl_matches_chunks_schema", "FTS5 DDLがchunk schemaと一致する", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("fts5_match_query_builder_escapes_operators", "FTS5演算子をリテラル化する", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("fts5_empty_query_returns_empty_result", "空queryで検索しない", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("knowledge_allowed_roles_json_required", "allowed_rolesをSQLで評価する", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("knowledge_source_types_json_each", "source_typesをjson_eachで評価する", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("citation_excerpt_retention_redacts_sources_panel", "保持期限後にsource本文をredactする", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("approval_expiration_finalizes_run", "期限切れapprovalだけならrunをfinalizeする", "completed", "completed", 0, 0, None),
    AgentEvaluationCase("high_importance_claims_extracted_from_sections", "重要主張をclaimsへ抽出する", "waiting_for_approval", "waiting_for_approval", 0, 0, "valid", expected_artifact_json_path=["claims_json"]),
    AgentEvaluationCase("worker_fresh_auth_recheck_after_scope_change", "workerが最新権限で再確認する", "failed", "failed", 0, 0, None, expected_error_code="agent_worker_failed"),
    AgentEvaluationCase("idempotency_stale_in_progress_reaper_returns_failure_response", "stale in_progressをreaperが解決する", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("idempotency_stale_same_key_returns_stored_failure_response", "stale後同一keyに保存済み応答を返す", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("fts5_japanese_exact_phrase_returns_matching_doc", "日本語完全一致検索を確認する", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
    AgentEvaluationCase("fts5_japanese_partial_match_known_limitation_documented", "日本語部分一致制約を文書化する", "waiting_for_approval", "waiting_for_approval", 0, 0, None),
)


def required_evaluation_case_ids() -> list[str]:
    return [case.id for case in REQUIRED_EVALUATION_CASES]


def validate_evaluation_case_registry() -> None:
    ids = required_evaluation_case_ids()
    if len(ids) != 51:
        raise AssertionError("Agent evaluation case count must be 51")
    duplicated = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicated:
        raise AssertionError(f"duplicated evaluation cases: {duplicated}")
    for case in REQUIRED_EVALUATION_CASES:
        if case.score_threshold != 1.0:
            raise AssertionError(f"{case.id} must require a full score")
