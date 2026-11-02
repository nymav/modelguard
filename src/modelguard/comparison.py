"""Pair by immutable case identity, never by list position or aggregate alone."""
from math import isclose
from .config import GuardError, Thresholds
from .models import Run
from .statistics import exact_mcnemar
from .scoring import summarize

def validate_run(run: Run):
    ids=[c.case_id for c in run.cases]
    if not ids or len(ids)!=len(set(ids)) or set(ids)!=set(run.case_hashes): raise GuardError('Run case coverage is inconsistent')
    if run.summary != summarize(run.cases): raise GuardError('Stored summary does not match case evidence')
    for c in run.cases:
        expected_category=bool(c.prediction and c.prediction.category == c.expected.category)
        expected_pass=expected_category and c.error is None and (run.judge_policy == 'category_only' or (c.summary_score is not None and c.summary_score >= run.min_summary_score))
        if c.category_correct != expected_category or c.passed != expected_pass:
            raise GuardError('Stored case scoring is inconsistent')
    return run

def compare(baseline: Run, candidate: Run, thresholds: Thresholds) -> dict:
    validate_run(baseline); validate_run(candidate); thresholds.validate_order()
    for key in ['dataset_hash','case_hashes','provenance','provider','judge_policy','min_summary_score','engine_version']:
        if getattr(baseline,key)!=getattr(candidate,key): raise GuardError('Incompatible runs: ' + key)
    if baseline.summary['errors']: raise GuardError('Baseline contains operational errors; choose a valid baseline')
    old={c.case_id:c for c in baseline.cases}; new={c.case_id:c for c in candidate.cases}
    if any(old[i].expected != new[i].expected or old[i].difficulty != new[i].difficulty for i in old):
        raise GuardError('Run labels or difficulty metadata do not match')
    regressions=[i for i in old if old[i].passed and not new[i].passed]
    improvements=[i for i in old if not old[i].passed and new[i].passed]
    delta=candidate.summary['pass_rate']-baseline.summary['pass_rate']; drop=-delta
    # Thresholds are practical gates, not a significance test.
    severity='critical' if drop >= thresholds.critical_drop - 1e-12 else 'warning' if drop >= thresholds.warn_drop - 1e-12 else 'pass'
    if candidate.summary['errors']: severity='error'
    per_category={category: {
        'baseline': baseline.summary['per_category'][category],
        'candidate': candidate.summary['per_category'][category],
        'delta': (candidate.summary['per_category'][category]['accuracy'] - baseline.summary['per_category'][category]['accuracy']) if baseline.summary['per_category'][category]['n'] else None,
    } for category in ['billing','technical','account','general']}
    return {'schema_version':1,'baseline_id':baseline.id,'candidate_id':candidate.id,
        'status':severity,'delta':delta,'regressions':regressions,'improvements':improvements,
        'unchanged_pass':sum(old[i].passed and new[i].passed for i in old),
        'unchanged_fail':sum(not old[i].passed and not new[i].passed for i in old),
        'mcnemar_exact_p':exact_mcnemar(len(regressions),len(improvements)),
        'thresholds':thresholds.model_dump(),'per_category':per_category,
        'provenance':candidate.provenance,
        'release_evidence':candidate.provenance == 'human_reviewed' and candidate.provider == 'openai'}

def slow_drift(history: list[Run], current: Run, thresholds: Thresholds) -> dict:
    compatible=[r for r in history if r.id!=current.id and r.created_at <= current.created_at and
        all(getattr(r,k)==getattr(current,k) for k in ['dataset_hash','provider','judge_policy','min_summary_score','engine_version'])]
    compatible=sorted(compatible,key=lambda r:(r.created_at,r.id))
    window=(compatible+[current])[-thresholds.drift_window:]
    for run in window: validate_run(run)
    if any(r.summary['errors'] for r in window): return {'status':'unavailable','reason':'Operational errors in drift window'}
    if len(window)<thresholds.drift_window: return {'status':'insufficient_history','runs':len(window),'required':thresholds.drift_window}
    average=sum(r.summary['pass_rate'] for r in window)/len(window)
    return {'status':'warning' if average < thresholds.drift_floor else 'pass',
        'runs':len(window),'moving_average':average,'floor':thresholds.drift_floor,
        'run_ids':[r.id for r in window]}
