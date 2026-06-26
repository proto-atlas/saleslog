import json
import os
import subprocess
from typing import Protocol

import httpx

from app.agent.output_schema import AgentLLMOutput, agent_output_json_schema
from app.enums import AgentActionType
from app.models import Customer, Visit
from app.settings import AgentLLMConfigError, AgentLLMSettings, get_agent_llm_settings

PROMPT_VERSION = "agent_v8_2026_06_16"
SCHEMA_VERSION = "agent_output_v1"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_OUTPUT_TOOL_NAME = "submit_saleslog_agent_output"
HTTP_TIMEOUT_SECONDS = 60
LLM_HTTP_TRANSPORT_ENV = "AGENT_LLM_HTTP_TRANSPORT"
POWERSHELL_HTTP_ERROR_PREFIX = "llm_http_error:"
POWERSHELL_TRANSPORT = "powershell"
HTTPX_TRANSPORT = "httpx"
WINDOWS_OS_NAME = "nt"

POWERSHELL_POST_JSON_SCRIPT = r"""
$ErrorActionPreference = "Stop"
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$payloadText = [Console]::In.ReadToEnd()
$payload = $payloadText | ConvertFrom-Json
$headers = @{}
if ($null -ne $payload.headers) {
  foreach ($property in $payload.headers.PSObject.Properties) {
    $headers[$property.Name] = [string]$property.Value
  }
}
$body = $payload.body | ConvertTo-Json -Depth 100 -Compress
$bodyBytes = [System.Text.UTF8Encoding]::new($false).GetBytes($body)
$responseBodyPath = [System.IO.Path]::GetTempFileName()
try {
  $response = Invoke-WebRequest `
    -UseBasicParsing `
    -Uri ([string]$payload.url) `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json; charset=utf-8" `
    -Body $bodyBytes `
    -TimeoutSec ([int]$payload.timeout) `
    -OutFile $responseBodyPath
  $responseBytes = [System.IO.File]::ReadAllBytes($responseBodyPath)
  [Console]::OpenStandardOutput().Write($responseBytes, 0, $responseBytes.Length)
} catch {
  $statusCode = 0
  $errorBody = $_.Exception.Message
  if ($null -ne $_.Exception.Response) {
    try {
      $statusCode = [int]$_.Exception.Response.StatusCode
    } catch {}
    try {
      $stream = $_.Exception.Response.GetResponseStream()
      if ($null -ne $stream) {
        $reader = New-Object System.IO.StreamReader($stream, [System.Text.UTF8Encoding]::new($false), $true)
        $errorBody = $reader.ReadToEnd()
      }
    } catch {}
  }
  [Console]::Error.Write("llm_http_error:" + $statusCode + ":" + $errorBody)
  exit 22
} finally {
  Remove-Item -LiteralPath $responseBodyPath -ErrorAction SilentlyContinue
}
"""


class LLMProviderError(RuntimeError):
    pass


class LLMProvider(Protocol):
    provider: str
    model: str
    prompt_version: str
    schema_version: str
    model_params: dict[str, object]

    def generate(
        self,
        *,
        customer: Customer,
        visits: list[Visit],
        knowledge_results: list[dict[str, object]],
    ) -> AgentLLMOutput:
        ...


class MockLLMProvider:
    provider = "mock"
    model = "mock-llm"
    prompt_version = PROMPT_VERSION
    schema_version = SCHEMA_VERSION
    model_params: dict[str, object] = {}

    def generate(
        self,
        *,
        customer: Customer,
        visits: list[Visit],
        knowledge_results: list[dict[str, object]],
    ) -> AgentLLMOutput:
        latest_visit = visits[0] if visits else None
        visit_memo = latest_visit.memo if latest_visit is not None else None
        claim_text = (
            f"直近の活動履歴に「{visit_memo}」と記録されています"
            if visit_memo
            else "活動履歴が少ないため、追加確認が必要です"
        )
        claims: list[dict[str, object]] = [
            {
                "claim_id": "claim_001",
                "text": claim_text,
                "importance": "high" if visit_memo else "medium",
                "requires_citation": bool(visit_memo),
                "citation_ids": [],
            }
        ]
        candidates: list[dict[str, object]] = []
        if latest_visit is not None and visit_memo:
            candidates.append(
                {
                    "candidate_id": "cand_001",
                    "claim_id": "claim_001",
                    "source_type": "activity",
                    "source_id": str(latest_visit.id),
                    "chunk_id": None,
                    "quoted_text": visit_memo,
                    "label": "活動ログ",
                }
            )
        output = {
            "customer_summary": {
                "text": f"{customer.name} の商談準備メモです。",
                "claim_ids": ["claim_001"],
            },
            "meeting_brief": {
                "text": "過去の活動履歴と社内ナレッジを確認し、次回確認事項を整理しました。",
                "claim_ids": ["claim_001"],
            },
            "risks": [
                {
                    "title": "確認不足のリスク",
                    "reason": "直近履歴を前提に、未確認事項を商談で確認する必要があります。",
                    "severity": "medium",
                    "claim_ids": ["claim_001"],
                }
            ],
            "opportunities": [
                {
                    "title": "次回接点の具体化",
                    "reason": "商談後のフォローをタスクとして残せます。",
                    "claim_ids": ["claim_001"],
                }
            ],
            "suggested_questions": [
                {
                    "question": "現在の優先課題は何ですか。",
                    "reason": "次アクションを顧客状況に合わせるため。",
                }
            ],
            "suggested_next_actions": [
                {
                    "action_type": AgentActionType.task.value,
                    "title": f"{customer.name} への次回フォロー",
                    "description": "商談後に確認事項と次回提案内容を整理する。",
                    "requires_approval": True,
                    "claim_ids": ["claim_001"],
                },
                {
                    "action_type": AgentActionType.memo.value,
                    "title": f"{customer.name} 商談メモ",
                    "description": "商談前の確認事項と想定リスクを保存する。",
                    "requires_approval": True,
                    "claim_ids": ["claim_001"],
                },
            ],
            "follow_up_email_draft": {
                "subject": f"{customer.name} 商談後のご確認",
                "body": "本日はお時間をいただきありがとうございました。確認事項を整理して改めてご連絡します。",
                "claim_ids": ["claim_001"],
            },
            "claims": claims,
            "citation_candidates": candidates,
            "uncertainties": [
                {
                    "claim_id": None,
                    "message_key": "knowledge_result_count",
                    "text": f"参照できたナレッジは {len(knowledge_results)} 件です。",
                }
            ],
        }
        return AgentLLMOutput.model_validate(output)


class OpenAIProvider:
    provider = "openai"
    prompt_version = PROMPT_VERSION
    schema_version = SCHEMA_VERSION

    def __init__(self, *, settings: AgentLLMSettings) -> None:
        if settings.openai_api_key is None:
            raise LLMProviderError("openai_api_key_missing")
        if settings.openai_model == "":
            raise LLMProviderError("openai_model_missing")
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.model_params = _model_params(
            settings, include_temperature=True, token_key="max_output_tokens"
        )

    def generate(
        self,
        *,
        customer: Customer,
        visits: list[Visit],
        knowledge_results: list[dict[str, object]],
    ) -> AgentLLMOutput:
        body = _openai_request_body(
            self.model,
            self.model_params,
            customer=customer,
            visits=visits,
            knowledge_results=knowledge_results,
        )
        data = _post_json(
            OPENAI_RESPONSES_URL,
            body,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        text = _extract_openai_text(data)
        return AgentLLMOutput.model_validate(json.loads(text))


class AnthropicProvider:
    provider = "anthropic"
    prompt_version = PROMPT_VERSION
    schema_version = SCHEMA_VERSION

    def __init__(self, *, settings: AgentLLMSettings) -> None:
        if settings.anthropic_api_key is None:
            raise LLMProviderError("anthropic_api_key_missing")
        self.api_key = settings.anthropic_api_key
        self.model = settings.anthropic_model
        self.model_params = _model_params(
            settings,
            include_temperature=_anthropic_supports_temperature(settings.anthropic_model),
            token_key="max_tokens",
        )

    def generate(
        self,
        *,
        customer: Customer,
        visits: list[Visit],
        knowledge_results: list[dict[str, object]],
    ) -> AgentLLMOutput:
        body = _anthropic_request_body(
            self.model,
            self.model_params,
            customer=customer,
            visits=visits,
            knowledge_results=knowledge_results,
        )
        data = _post_json(
            ANTHROPIC_MESSAGES_URL,
            body,
            {
                "x-api-key": self.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
        )
        return AgentLLMOutput.model_validate(_extract_anthropic_tool_input(data))


def select_llm_provider() -> LLMProvider:
    provider_name = os.environ.get("AGENT_LLM_PROVIDER", "mock").strip().lower()
    if provider_name == "mock":
        return MockLLMProvider()
    try:
        settings = get_agent_llm_settings()
    except AgentLLMConfigError as error:
        raise LLMProviderError(error.code) from error
    if settings.provider == "openai":
        return OpenAIProvider(settings=settings)
    if settings.provider == "anthropic":
        return AnthropicProvider(settings=settings)
    raise LLMProviderError("agent_llm_provider_unsupported")


def _model_params(
    settings: AgentLLMSettings, *, include_temperature: bool, token_key: str
) -> dict[str, object]:
    params: dict[str, object] = {token_key: settings.max_tokens}
    if include_temperature and settings.temperature is not None:
        params["temperature"] = settings.temperature
    return params


def _anthropic_supports_temperature(model: str) -> bool:
    normalized = model.lower().replace("_", "-")
    family = "opus"
    unsupported_markers = (
        f"{family}-4-7",
        f"{family}-4.7",
        f"{family}-4-8",
        f"{family}-4.8",
    )
    return not any(marker in normalized for marker in unsupported_markers)


def _openai_request_body(
    model: str,
    model_params: dict[str, object],
    *,
    customer: Customer,
    visits: list[Visit],
    knowledge_results: list[dict[str, object]],
) -> dict[str, object]:
    body: dict[str, object] = {
        "model": model,
        "instructions": _system_prompt(),
        "input": _user_prompt(customer, visits, knowledge_results),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "saleslog_agent_output",
                "strict": True,
                "schema": agent_output_json_schema(),
            }
        },
    }
    body.update(model_params)
    return body


def _anthropic_request_body(
    model: str,
    model_params: dict[str, object],
    *,
    customer: Customer,
    visits: list[Visit],
    knowledge_results: list[dict[str, object]],
) -> dict[str, object]:
    max_tokens_value = model_params.get("max_tokens", 4096)
    max_tokens = max_tokens_value if isinstance(max_tokens_value, int) else 4096
    body: dict[str, object] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": _system_prompt(),
        "messages": [
            {
                "role": "user",
                "content": _user_prompt(customer, visits, knowledge_results),
            }
        ],
        "tools": [
            {
                "name": ANTHROPIC_OUTPUT_TOOL_NAME,
                "description": (
                    "Saleslog Agentの固定workflowで保存する成果物を返す。"
                    "認可判断やDB書き込みは行わず、入力に含まれるsourceだけを根拠にする。"
                ),
                # strict tool use はこのスキーマだと "grammar too large" で400になるため使わない。
                # tool_choice で当該 tool を強制し、出力は worker の AgentLLMOutput 検証(+リトライ)で担保する。
                "input_schema": agent_output_json_schema(),
            }
        ],
        "tool_choice": {"type": "tool", "name": ANTHROPIC_OUTPUT_TOOL_NAME},
    }
    if "temperature" in model_params:
        body["temperature"] = model_params["temperature"]
    return body


def _system_prompt() -> str:
    return (
        "あなたは営業CRMの固定ワークフロー内で、参照済みsourceだけを使って商談準備を作成します。"
        "出力JSON内の自然文はすべて日本語で書いてください。"
        "固有名詞、source_type、ID、enum値は入力値のまま保持してください。"
        "認可判断、DB書き込み、tool実行可否は行いません。"
        "citation_candidates.quoted_text は提示されたsource本文から逐語コピーしてください。"
        "重要なリスク、契約、価格、顧客意図、失注可能性、次アクションの主張はclaimsへ抽出してください。"
    )


def _user_prompt(
    customer: Customer,
    visits: list[Visit],
    knowledge_results: list[dict[str, object]],
) -> str:
    context = {
        "output_language": "ja-JP",
        "customer": {
            "source_type": "customer",
            "source_id": str(customer.id),
            "name": customer.name,
            "status": customer.status.value,
        },
        "activities": [
            {
                "source_type": "activity",
                "source_id": str(visit.id),
                "label": f"活動ログ: {visit.visited_at.date().isoformat()}",
                "body": visit.memo or f"{visit.activity_type.value} / {visit.status.value}",
            }
            for visit in visits
        ],
        "knowledge": [
            {
                "source_type": str(result["source_type"]),
                "source_id": str(result["doc_id"]),
                "chunk_id": str(result["chunk_id"]),
                "label": str(result["title"]),
                "body": str(result["text"]),
            }
            for result in knowledge_results
        ],
    }
    return json.dumps(context, ensure_ascii=False)


def _post_json(
    url: str, body: dict[str, object], headers: dict[str, str]
) -> dict[str, object]:
    transport = _llm_http_transport()
    if transport == POWERSHELL_TRANSPORT:
        return _post_json_with_powershell(url, body, headers)
    return _post_json_with_httpx(url, body, headers)


def _llm_http_transport() -> str:
    configured = os.environ.get(LLM_HTTP_TRANSPORT_ENV, "").strip().lower()
    if configured in (POWERSHELL_TRANSPORT, HTTPX_TRANSPORT):
        return configured
    if os.name == WINDOWS_OS_NAME:
        return POWERSHELL_TRANSPORT
    return HTTPX_TRANSPORT


def _post_json_with_httpx(
    url: str, body: dict[str, object], headers: dict[str, str]
) -> dict[str, object]:
    try:
        response = httpx.post(
            url,
            json=body,
            headers=headers,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise LLMProviderError(
            _llm_http_status_error_code(error.response.status_code)
        ) from error
    except httpx.RequestError as error:
        raise LLMProviderError("llm_network_error") from error
    try:
        decoded = response.json()
    except json.JSONDecodeError as error:
        raise LLMProviderError("llm_response_json_invalid") from error
    if not isinstance(decoded, dict):
        raise LLMProviderError("llm_response_not_object")
    return decoded


def _post_json_with_powershell(
    url: str, body: dict[str, object], headers: dict[str, str]
) -> dict[str, object]:
    payload = {
        "url": url,
        "body": body,
        "headers": _headers_without_content_type(headers),
        "timeout": HTTP_TIMEOUT_SECONDS,
    }
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                POWERSHELL_POST_JSON_SCRIPT,
            ],
            input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            capture_output=True,
            timeout=HTTP_TIMEOUT_SECONDS + 10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError, IndexError) as error:
        raise LLMProviderError("llm_powershell_transport_failed") from error
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    if completed.returncode != 0:
        detail = stderr.strip() or stdout.strip()
        raise LLMProviderError(
            _powershell_transport_error_code(detail)
            or "llm_powershell_transport_failed"
        )
    try:
        decoded = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise LLMProviderError("llm_response_json_invalid") from error
    if not isinstance(decoded, dict):
        raise LLMProviderError("llm_response_not_object")
    return decoded


def _headers_without_content_type(headers: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() != "content-type"}


def _powershell_transport_error_code(detail: str) -> str | None:
    if not detail.startswith(POWERSHELL_HTTP_ERROR_PREFIX):
        return None
    parts = detail.split(":", 2)
    if len(parts) < 2:
        return "llm_http_error"
    try:
        status_code = int(parts[1])
    except ValueError:
        return "llm_http_error"
    return _llm_http_status_error_code(status_code)


def _llm_http_status_error_code(status_code: int) -> str:
    if status_code in (401, 403):
        return "llm_auth_failed"
    if status_code == 404:
        return "llm_model_not_found"
    if status_code == 429:
        return "llm_rate_limited"
    if status_code == 400:
        return "llm_bad_request"
    if status_code >= 500:
        return "llm_upstream_unavailable"
    return "llm_http_error"


def _extract_openai_text(data: dict[str, object]) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str):
        return output_text
    output = data.get("output")
    if not isinstance(output, list):
        raise LLMProviderError("openai_output_missing")
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "output_text":
                text = part.get("text")
                if isinstance(text, str):
                    return text
    raise LLMProviderError("openai_output_text_missing")


def _extract_anthropic_tool_input(data: dict[str, object]) -> dict[str, object]:
    content = data.get("content")
    if not isinstance(content, list):
        raise LLMProviderError("anthropic_content_missing")
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") != "tool_use" or part.get("name") != ANTHROPIC_OUTPUT_TOOL_NAME:
            continue
        input_value = part.get("input")
        if isinstance(input_value, dict):
            return input_value
        raise LLMProviderError("anthropic_tool_input_not_object")
    raise LLMProviderError("anthropic_tool_input_missing")
