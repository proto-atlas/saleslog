import os


class AgentFaultInjected(RuntimeError):
    pass


AGENT_FAULT_HOOKS: tuple[str, ...] = (
    "db_transaction_failure_hook",
    "business_record_inserted_but_approval_update_failed_hook",
    "idempotency_record_created_then_process_crashed_hook",
    "idempotency_existing_in_progress_hook",
    "idempotency_lease_expired_while_original_process_alive_hook",
    "approval_payload_validation_failure_hook",
    "worker_heartbeat_stopped_hook",
    "sse_event_write_failed_hook",
    "fts5_match_syntax_error_hook",
)


def agent_fault_enabled(name: str) -> bool:
    raw = os.environ.get("AGENT_FAULT_HOOKS", "")
    enabled = {item.strip() for item in raw.split(",") if item.strip()}
    return name in enabled


def maybe_raise_agent_fault(name: str) -> None:
    if agent_fault_enabled(name):
        raise AgentFaultInjected(name)
