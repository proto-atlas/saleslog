import enum


class UserRole(str, enum.Enum):
    sales = "sales"
    manager = "manager"


class CustomerStatus(str, enum.Enum):
    prospect = "prospect"
    negotiating = "negotiating"
    won = "won"
    lost = "lost"
    dormant = "dormant"


class CustomerArea(str, enum.Enum):
    tokyo = "tokyo"
    kanagawa = "kanagawa"
    saitama = "saitama"
    chiba = "chiba"
    other = "other"


class ActivityType(str, enum.Enum):
    visit = "visit"
    call = "call"
    email = "email"
    online = "online"


class VisitStatus(str, enum.Enum):
    planned = "planned"
    done = "done"
    cancelled = "cancelled"


class AgentWorkflowType(str, enum.Enum):
    meeting_prep = "meeting_prep"
    risk_review = "risk_review"
    follow_up = "follow_up"


class AgentRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    waiting_for_approval = "waiting_for_approval"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AgentStepStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class AgentApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    edited_and_approved = "edited_and_approved"
    rejected = "rejected"
    persisted = "persisted"
    persist_failed = "persist_failed"
    expired = "expired"
    cancelled = "cancelled"


class AgentActionType(str, enum.Enum):
    activity_log = "activity_log"
    task = "task"
    memo = "memo"
    email_draft = "email_draft"


class AgentIdempotencyStatus(str, enum.Enum):
    in_progress = "in_progress"
    succeeded = "succeeded"
    failed = "failed"


class AgentIdempotencyFailureKind(str, enum.Enum):
    retryable_before_side_effect = "retryable_before_side_effect"
    permanent = "permanent"
    unknown_after_possible_side_effect = "unknown_after_possible_side_effect"


class KnowledgeVisibility(str, enum.Enum):
    all_sales = "all_sales"
    managers_only = "managers_only"
    owner_team = "owner_team"
    customer_scoped = "customer_scoped"
    private = "private"
