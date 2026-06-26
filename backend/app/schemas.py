import json
from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_serializer, field_validator

from app.enums import (
    AgentActionType,
    AgentApprovalStatus,
    AgentRunStatus,
    AgentWorkflowType,
    ActivityType,
    CustomerArea,
    CustomerStatus,
    UserRole,
    VisitStatus,
)

T = TypeVar("T")

# 承認編集は人が画面で確認する短文 payload に限定する。
# body 最大 5,000 文字と claim_ids を含めても十分な余白を持たせる。
AGENT_APPROVAL_PATCH_MAX_BYTES = 24_000
AGENT_APPROVAL_PATCH_MAX_DEPTH = 4
AGENT_APPROVAL_PATCH_MAX_OBJECT_KEYS = 16
AGENT_APPROVAL_PATCH_MAX_ARRAY_ITEMS = 50
AGENT_APPROVAL_PATCH_MAX_STRING_LENGTH = 5_000


def _to_utc_z(value: datetime) -> str:
    # naive UTC 格納値を ISO 8601 の Z 表記で返す
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_json_shape(value: object, *, depth: int = 0) -> None:
    if depth > AGENT_APPROVAL_PATCH_MAX_DEPTH:
        raise ValueError("edited_payload_json_too_deep")
    if isinstance(value, dict):
        if len(value) > AGENT_APPROVAL_PATCH_MAX_OBJECT_KEYS:
            raise ValueError("edited_payload_json_too_many_keys")
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("edited_payload_json_invalid_key")
            _validate_json_shape(child, depth=depth + 1)
        return
    if isinstance(value, list):
        if len(value) > AGENT_APPROVAL_PATCH_MAX_ARRAY_ITEMS:
            raise ValueError("edited_payload_json_array_too_long")
        for child in value:
            _validate_json_shape(child, depth=depth + 1)
        return
    if isinstance(value, str) and len(value) > AGENT_APPROVAL_PATCH_MAX_STRING_LENGTH:
        raise ValueError("edited_payload_json_string_too_long")
    if value is None or isinstance(value, bool | int | float | str):
        return
    raise ValueError("edited_payload_json_invalid_value")


def _validate_agent_approval_patch_payload(value: dict[str, object]) -> dict[str, object]:
    _validate_json_shape(value)
    try:
        payload_size = len(
            json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
    except (TypeError, ValueError) as error:
        raise ValueError("edited_payload_json_invalid_value") from error
    if payload_size > AGENT_APPROVAL_PATCH_MAX_BYTES:
        raise ValueError("edited_payload_json_too_large")
    return value


class ListResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class ErrorDetailResponse(BaseModel):
    detail: str


class UserOut(BaseModel):
    id: int
    name: str
    role: UserRole
    # 認証プロバイダと紐付け済みか（subject の生値は返さない。認証仕様）。
    # 管理用途（manager）のみ bool、担当者 lookup では null（情報を返さない）
    linked: bool | None = None


class UserListItem(BaseModel):
    id: int
    name: str
    role: UserRole | None = None
    linked: bool | None = None


class UsersResponse(BaseModel):
    items: list[UserListItem]


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: UserRole

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class UserPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    role: UserRole | None = None
    # 認証プロバイダの subject。null で紐付け解除（空文字は認証経路に乗せない）
    external_id: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("external_id", mode="before")
    @classmethod
    def strip_external_id(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    address: str | None = Field(default=None, max_length=200)
    area: CustomerArea
    status: CustomerStatus
    # 省略時はサーバ側で現在ユーザーを採用する
    owner_id: int | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        # trim 後に長さ制約を評価する（空白のみ → 空文字 → 422。仕様）
        return value.strip() if isinstance(value, str) else value

    @field_validator("address", mode="before")
    @classmethod
    def empty_address_to_none(cls, value: object) -> object:
        # 空文字での住所クリアは null に正規化（表示・削除判定を null に一本化）
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


class CustomerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    address: str | None = Field(default=None, max_length=200)
    area: CustomerArea | None = None
    status: CustomerStatus | None = None
    owner_id: int | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("address", mode="before")
    @classmethod
    def empty_address_to_none(cls, value: object) -> object:
        # 空文字での住所クリアは null に正規化（CustomerCreate と同じ規則）
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


class CustomerOut(BaseModel):
    id: int
    name: str
    address: str | None
    area: CustomerArea
    status: CustomerStatus
    owner_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return _to_utc_z(value)


class CustomerListItem(CustomerOut):
    # 一覧専用: 当該顧客の最新 visit の visited_at（無ければ null。仕様）
    last_visited_at: datetime | None

    @field_serializer("last_visited_at")
    def serialize_last_visited_at(self, value: datetime | None) -> str | None:
        return _to_utc_z(value) if value is not None else None


def _to_naive_utc(value: datetime) -> datetime:
    # tz 付きの入力を UTC に揃えて naive で格納する（DB は UTC 固定。仕様）
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class VisitCreate(BaseModel):
    customer_id: int
    activity_type: ActivityType
    status: VisitStatus
    visited_at: datetime
    memo: str | None = Field(default=None, max_length=2000)

    @field_validator("visited_at")
    @classmethod
    def visited_at_requires_timezone(cls, value: datetime) -> datetime:
        # ISO 8601 UTC 必須。タイムゾーンなしは 422
        if value.tzinfo is None:
            raise ValueError("タイムゾーン付きの ISO 8601 形式で指定してください")
        return _to_naive_utc(value)


class VisitPatch(BaseModel):
    # user_id / customer_id は変更不可（送られても無視する。仕様）
    activity_type: ActivityType | None = None
    status: VisitStatus | None = None
    visited_at: datetime | None = None
    memo: str | None = Field(default=None, max_length=2000)

    @field_validator("visited_at")
    @classmethod
    def visited_at_requires_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("タイムゾーン付きの ISO 8601 形式で指定してください")
        return _to_naive_utc(value)


class VisitOut(BaseModel):
    id: int
    customer_id: int
    user_id: int
    activity_type: ActivityType
    status: VisitStatus
    visited_at: datetime
    memo: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("visited_at", "created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return _to_utc_z(value)


class TrendPoint(BaseModel):
    month: str
    count: int


class AreaCount(BaseModel):
    area: CustomerArea
    count: int


class OwnerCount(BaseModel):
    owner_id: int
    owner_name: str
    count: int


class TodayVisit(BaseModel):
    # 集計用 denormalized 形のため参照キーは visit_id
    visit_id: int
    customer_id: int
    customer_name: str
    owner_id: int
    visited_at: datetime
    status: VisitStatus

    @field_serializer("visited_at")
    def serialize_visited_at(self, value: datetime) -> str:
        return _to_utc_z(value)


class DashboardSummary(BaseModel):
    total_customers: int
    visits_this_month: int
    visits_trend: list[TrendPoint]
    by_area: list[AreaCount]
    by_owner: list[OwnerCount]
    unrecorded_count: int
    today_visits: list[TodayVisit]


class VisitListItem(BaseModel):
    # 一覧表示用の join 済み DTO。memo は含めない
    id: int
    customer_id: int
    customer_name: str
    owner_id: int
    user_id: int
    user_name: str
    activity_type: ActivityType
    status: VisitStatus
    visited_at: datetime
    created_at: datetime
    updated_at: datetime

    @field_serializer("visited_at", "created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return _to_utc_z(value)


class AgentRunCreate(BaseModel):
    objective: str = Field(min_length=1, max_length=500)
    workflow_type: AgentWorkflowType

    @field_validator("objective", mode="before")
    @classmethod
    def strip_objective(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AgentRunOut(BaseModel):
    id: int
    user_id: int
    customer_id: int
    workflow_type: AgentWorkflowType
    objective: str
    status: AgentRunStatus
    schema_version: str
    workflow_version: str
    prompt_version: str
    provider: str
    model: str
    model_params_json: dict[str, object]
    started_at: datetime | None
    completed_at: datetime | None
    latency_ms: int | None
    last_error_code: str | None
    last_error_message_safe: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("started_at", "completed_at", "created_at", "updated_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        return _to_utc_z(value) if value is not None else None


class AgentRunCreateResponse(BaseModel):
    run_id: int
    status: AgentRunStatus
    reused: bool = False


class AgentEventOut(BaseModel):
    id: int
    run_id: int
    event_seq: int
    step_no: int | None
    event_type: str
    status: str
    safe_message_key: str
    safe_message_params_json: dict[str, object]
    artifact_id: int | None
    approval_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return _to_utc_z(value)


class AgentArtifactOut(BaseModel):
    id: int
    run_id: int
    artifact_type: str
    content_json: dict[str, object]
    claims_json: list[dict[str, object]]
    citation_candidates_json: list[dict[str, object]]
    citations_json: list[dict[str, object]]
    uncertainties_json: list[dict[str, object]]
    schema_version: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return _to_utc_z(value)


class AgentRunSourceOut(BaseModel):
    id: int
    run_id: int
    source_type: str
    source_id: str
    source_version: str
    source_checksum: str
    chunk_id: str | None
    label: str
    char_start: int
    char_end: int
    offset_unit: str
    source_excerpt: str | None
    source_excerpt_redacted_at: datetime | None
    created_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}

    @field_serializer("source_excerpt_redacted_at", "created_at", "expires_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        return _to_utc_z(value) if value is not None else None


class AgentApprovalOut(BaseModel):
    id: int
    run_id: int
    customer_id: int
    version: int
    action_type: AgentActionType
    target_entity_type: str | None
    target_entity_id: int | None
    business_record_type: str | None
    business_record_id: int | None
    original_payload_json: dict[str, object]
    edited_payload_json: dict[str, object] | None
    approved_payload_json: dict[str, object] | None
    payload_schema_version: str
    status: AgentApprovalStatus
    decided_by: int | None
    decided_at: datetime | None
    persisted_at: datetime | None
    persist_error: str | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer(
        "decided_at", "persisted_at", "expires_at", "created_at", "updated_at"
    )
    def serialize_datetime(self, value: datetime | None) -> str | None:
        return _to_utc_z(value) if value is not None else None


class AgentApprovalPatch(BaseModel):
    version: int = Field(ge=1)
    edited_payload_json: dict[str, object]

    @field_validator("edited_payload_json")
    @classmethod
    def validate_edited_payload_json(
        cls, value: dict[str, object]
    ) -> dict[str, object]:
        return _validate_agent_approval_patch_payload(value)


class AgentApprovalDecision(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=80)
    version: int = Field(ge=1)


class AgentApprovalDecisionApproval(BaseModel):
    id: int
    run_id: int
    customer_id: int
    version: int
    action_type: AgentActionType
    business_record_type: str | None = None
    business_record_id: int | None = None
    status: AgentApprovalStatus


class AgentApprovalDecisionResponse(BaseModel):
    approval: AgentApprovalDecisionApproval
    status_code: int
    message_key: str
    retry_with_new_idempotency_key: bool = False
    requires_reconciliation: bool = False


class AgentApprovalDecisionError(BaseModel):
    code: str
    message_key: str
    retry_with_new_idempotency_key: bool
    requires_reconciliation: bool


class AgentApprovalDecisionErrorResponse(BaseModel):
    error: AgentApprovalDecisionError
