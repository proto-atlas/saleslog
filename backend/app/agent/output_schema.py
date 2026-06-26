from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_AGENT_OUTPUT_LIST_ITEMS = 20
MAX_AGENT_OUTPUT_CLAIM_IDS = 20
MAX_AGENT_OUTPUT_ID_LENGTH = 80

AgentOutputId = Annotated[
    str, Field(min_length=1, max_length=MAX_AGENT_OUTPUT_ID_LENGTH)
]


class AgentTextSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    claim_ids: list[AgentOutputId] = Field(max_length=MAX_AGENT_OUTPUT_CLAIM_IDS)


class AgentRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=2000)
    severity: Literal["low", "medium", "high"]
    claim_ids: list[AgentOutputId] = Field(max_length=MAX_AGENT_OUTPUT_CLAIM_IDS)


class AgentOpportunity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=2000)
    claim_ids: list[AgentOutputId] = Field(max_length=MAX_AGENT_OUTPUT_CLAIM_IDS)


class AgentQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=1000)


class AgentNextAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: Literal["activity_log", "task", "memo", "email_draft"]
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    requires_approval: bool
    claim_ids: list[AgentOutputId] = Field(max_length=MAX_AGENT_OUTPUT_CLAIM_IDS)


class AgentEmailDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    claim_ids: list[AgentOutputId] = Field(max_length=MAX_AGENT_OUTPUT_CLAIM_IDS)


class AgentClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: AgentOutputId
    text: str = Field(min_length=1, max_length=2000)
    importance: Literal["low", "medium", "high"]
    requires_citation: bool
    citation_ids: list[AgentOutputId] = Field(
        default_factory=list, max_length=MAX_AGENT_OUTPUT_CLAIM_IDS
    )


class AgentCitationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: AgentOutputId
    claim_id: AgentOutputId
    source_type: str = Field(min_length=1, max_length=40)
    source_id: str = Field(min_length=1, max_length=80)
    chunk_id: str | None = Field(default=None, max_length=80)
    quoted_text: str = Field(min_length=1, max_length=2000)
    label: str = Field(min_length=1, max_length=160)
    source_checksum: str | None = Field(default=None, max_length=80)


class AgentUncertainty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: AgentOutputId | None = None
    message_key: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=2000)


class AgentLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_summary: AgentTextSection
    meeting_brief: AgentTextSection
    risks: list[AgentRisk] = Field(max_length=MAX_AGENT_OUTPUT_LIST_ITEMS)
    opportunities: list[AgentOpportunity] = Field(max_length=MAX_AGENT_OUTPUT_LIST_ITEMS)
    suggested_questions: list[AgentQuestion] = Field(
        max_length=MAX_AGENT_OUTPUT_LIST_ITEMS
    )
    suggested_next_actions: list[AgentNextAction] = Field(
        max_length=MAX_AGENT_OUTPUT_LIST_ITEMS
    )
    follow_up_email_draft: AgentEmailDraft
    claims: list[AgentClaim] = Field(max_length=MAX_AGENT_OUTPUT_LIST_ITEMS)
    citation_candidates: list[AgentCitationCandidate] = Field(
        max_length=MAX_AGENT_OUTPUT_LIST_ITEMS
    )
    uncertainties: list[AgentUncertainty] = Field(
        default_factory=list, max_length=MAX_AGENT_OUTPUT_LIST_ITEMS
    )


def agent_output_json_schema() -> dict[str, object]:
    return AgentLLMOutput.model_json_schema()
