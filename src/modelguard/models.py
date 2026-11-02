"""Strict contracts shared by providers, reports and persisted evaluations."""
from __future__ import annotations
from typing import Literal
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, field_validator

Category = Literal['billing', 'technical', 'account', 'general']
class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)

class Prediction(Strict):
    category: Category
    summary: str = Field(min_length=1, max_length=600)
    @field_validator('summary')
    @classmethod
    def concise(cls, value: str) -> str:
        if not value.strip() or '\n' in value or '\r' in value:
            raise ValueError('Summary must be nonempty and single-line')
        return value

class Case(Strict):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    email: str = Field(min_length=1, max_length=12000)
    expected: Prediction
    difficulty: Literal['normal', 'ambiguous', 'short', 'typos', 'mixed_language', 'sarcastic', 'adversarial']
    notes: str = Field(min_length=1, max_length=3000)
    reviewed_by: str | None = None
    reviewed_at: str | None = None

class Dataset(Strict):
    schema_version: Literal[1]
    version: str = Field(min_length=1, max_length=100)
    provenance: Literal['human_reviewed', 'synthetic_fixture']
    description: str = Field(min_length=1, max_length=3000)
    cases: list[Case] = Field(min_length=1, max_length=2000)

class JudgeOutput(Strict):
    score: int = Field(ge=1, le=5)
    reason: str = Field(min_length=1, max_length=1500)

class Usage(Strict):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)

class Observation(Strict):
    raw: str
    usage: Usage | None = None
    elapsed_ms: float | None = Field(default=None, ge=0)
    response_id: str | None = None
    resolved_model: str | None = None
    attempts: int = Field(default=0, ge=0)

class CaseResult(Strict):
    case_id: str
    expected: Prediction
    difficulty: str
    prediction: Prediction | None = None
    raw: str | None = None
    category_correct: bool = False
    passed: bool = False
    summary_score: int | None = Field(default=None, ge=1, le=5)
    summary_reason: str | None = None
    classification: Observation | None = None
    judging: Observation | None = None
    error: str | None = None

class Run(Strict):
    schema_version: Literal[1] = 1
    id: str
    created_at: str
    dataset_hash: str
    dataset_version: str
    provenance: Literal['human_reviewed', 'synthetic_fixture']
    case_hashes: dict[str, str]
    prompt_version: str
    prompt_hash: str
    model: str
    provider: Literal['replay', 'openai']
    provider_fingerprint: str
    judge_policy: str
    min_summary_score: int = Field(ge=1, le=5)
    engine_version: str
    cases: list[CaseResult]
    summary: dict

    @field_validator('created_at')
    @classmethod
    def valid_timestamp(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None: raise ValueError('Run timestamp requires a timezone')
        return parsed.astimezone(timezone.utc).isoformat()
