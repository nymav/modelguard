"""Bounded asynchronous evaluation; every case yields a result, including errors."""
import asyncio
import platform
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import ValidationError
from . import __version__
from .models import Run, CaseResult, Prediction, JudgeOutput
from .config import GuardError
from .dataset import dataset_hash, case_hashes
from .providers import ProviderFailure
from .scoring import summarize
from .feature import classify_email

async def evaluate(prompt, dataset, provider, *, concurrency: int = 4,
                   min_summary_score: int = 3, category_only: bool = False) -> Run:
    if not 1 <= concurrency <= 16: raise GuardError('Concurrency must be 1–16')
    if not 1 <= min_summary_score <= 5: raise GuardError('Minimum summary score must be 1–5')
    example_inputs={' '.join(shot.email.lower().split()) for shot in prompt.few_shot}
    if any(' '.join(case.email.lower().split()) in example_inputs for case in dataset.cases):
        raise GuardError('Evaluation input appears in prompt few-shot examples')
    semaphore=asyncio.Semaphore(concurrency)
    async def one(case):
        result=CaseResult(case_id=case.id, expected=case.expected, difficulty=case.difficulty)
        stage='classification'
        async with semaphore:
            try:
                result.prediction,result.classification=await classify_email(case.email,prompt,provider,case_id=case.id)
                result.raw=result.classification.raw
                result.category_correct=result.prediction.category == case.expected.category
                if not category_only:
                    stage='judging'; result.judging=await provider.judge(case, result.prediction)
                    judge=JudgeOutput.model_validate_json(result.judging.raw)
                    result.summary_score=judge.score; result.summary_reason=judge.reason
                result.passed=result.category_correct and (category_only or result.summary_score >= min_summary_score)
            except ProviderFailure as exc:
                result.error=str(exc)
                if exc.observation:
                    setattr(result, stage, exc.observation)
                    if stage=='classification': result.raw=exc.observation.raw
            except ValidationError:
                result.error='invalid_' + ('prediction' if stage == 'classification' else 'judge_output')
            except (KeyError, TypeError, ValueError):
                result.error='invalid_provider_contract'
        return result
    cases=await asyncio.gather(*(one(case) for case in dataset.cases))
    return Run(id=uuid4().hex, created_at=datetime.now(timezone.utc).isoformat(),
        dataset_hash=dataset_hash(dataset), dataset_version=dataset.version, provenance=dataset.provenance,
        case_hashes=case_hashes(dataset), prompt_version=prompt.version, prompt_hash=prompt.fingerprint,
        model=provider.model, provider=provider.mode, provider_fingerprint=provider.fingerprint,
        judge_policy='category_only' if category_only else provider.judge_policy,
        min_summary_score=min_summary_score, engine_version=__version__, cases=cases, summary=summarize(cases))
