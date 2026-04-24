from typing import Any

from app.domain.models import LlmReportType

PROMPT_VERSION = "v1"

BASE_SYSTEM_PROMPT = """
You are the explanation layer for a personal US-listed securities trading assistant.
Return only strict JSON. Do not include markdown.
You explain the existing deterministic output.
You do not create orders, position sizing, or risk decisions.
Never add fields outside the requested schema.
Always keep risk_decision_locked true.
""".strip()


def universe_rationale_prompt(context: dict[str, Any]) -> tuple[str, str]:
    return (
        BASE_SYSTEM_PROMPT,
        f"""
Create a concise universe selection rationale report using this JSON context:
{context}

Required JSON schema:
{{
  "summary": "string",
  "key_drivers": ["string"],
  "risk_flags": ["string"],
  "selection_discipline": "string",
  "uncertainty": "string",
  "risk_decision_locked": true
}}
""".strip(),
    )


def trade_rationale_prompt(context: dict[str, Any]) -> tuple[str, str]:
    return (
        BASE_SYSTEM_PROMPT,
        f"""
Create a concise trade rationale report using this JSON context:
{context}

Required JSON schema:
{{
  "summary": "string",
  "setup": "string",
  "confirmations": ["string"],
  "invalidation_focus": "string",
  "risk_flags": ["string"],
  "uncertainty": "string",
  "risk_decision_locked": true
}}
Do not change or reinterpret the signal action, target weight, or risk policy.
""".strip(),
    )


def post_trade_review_prompt(context: dict[str, Any]) -> tuple[str, str]:
    return (
        BASE_SYSTEM_PROMPT,
        f"""
Create a concise post-trade review using this JSON context:
{context}

Required JSON schema:
{{
  "summary": "string",
  "outcome": "string",
  "what_worked": ["string"],
  "what_to_improve": ["string"],
  "follow_ups": ["string"],
  "uncertainty": "string",
  "risk_decision_locked": true
}}
""".strip(),
    )


def build_prompt(report_type: LlmReportType, context: dict[str, Any]) -> tuple[str, str]:
    if report_type == LlmReportType.UNIVERSE_RATIONALE:
        return universe_rationale_prompt(context)
    if report_type == LlmReportType.TRADE_RATIONALE:
        return trade_rationale_prompt(context)
    if report_type == LlmReportType.POST_TRADE_REVIEW:
        return post_trade_review_prompt(context)
    raise ValueError(f"Unsupported report type: {report_type}")
