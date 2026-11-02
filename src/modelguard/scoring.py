"""No imputed timings, tokens, judge ratings or model-quality claims."""
from statistics import mean
from .statistics import percentile, wilson
from .models import CaseResult

def summarize(cases: list[CaseResult]) -> dict:
    n = len(cases)
    if not n: raise ValueError('Cannot summarize an empty run')
    scores = [c.summary_score for c in cases if c.summary_score is not None]
    times = [c.classification.elapsed_ms for c in cases if c.classification and c.classification.elapsed_ms is not None]
    observations = [o for c in cases for o in (c.classification, c.judging) if o]
    usages = [o.usage for o in observations if o.usage]
    successes = sum(c.passed for c in cases)
    result = {
        'n': n, 'passed': successes, 'pass_rate': successes/n,
        'category_accuracy': sum(c.category_correct for c in cases)/n,
        'pass_rate_wilson_95': wilson(successes, n),
        'errors': sum(c.error is not None for c in cases),
        'summary_mean': mean(scores) if scores else None,
        'judged_cases': len(scores), 'classification_latency_samples': len(times),
        'classification_p50_ms': percentile(times, .50), 'classification_p95_ms': percentile(times, .95),
        'usage_observations': len(usages), 'total_observations': len(observations),
        'input_tokens': sum(u.input_tokens for u in usages) if usages else None,
        'output_tokens': sum(u.output_tokens for u in usages) if usages else None,
        'usage_complete': bool(observations) and len(usages) == len(observations) and all(o.attempts <= 1 for o in observations),
        'requests_attempted': sum(o.attempts for o in observations),
        'per_category': {},
    }
    for category in ['billing', 'technical', 'account', 'general']:
        group = [c for c in cases if c.expected.category == category]
        result['per_category'][category] = {'n': len(group), 'accuracy': sum(c.category_correct for c in group)/len(group) if group else None}
    return result
