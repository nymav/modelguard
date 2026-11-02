"""Exercise the real evaluation path with explicitly scripted provider outputs."""
from pathlib import Path
import json
from tempfile import TemporaryDirectory
from dataclasses import replace
from .config import load_prompt, Thresholds, GuardError
from .dataset import load_dataset
from .providers import ReplayProvider
from .runner import evaluate
from .scoring import summarize
from .comparison import compare, slow_drift
from .store import Store
from .reporting import atomic_text, write_report
from .notifications import slack_payload

async def demo(output: Path):
    root=Path.cwd()
    if not (root/'fixtures/dataset.json').is_file(): raise GuardError('Run the demo from the ModelGuard checkout')
    dataset=load_dataset(root/'fixtures/dataset.json'); output.mkdir(parents=True,exist_ok=True)
    thresholds=Thresholds(); store=Store(output/'history.sqlite')
    try:
        runs=[]
        for version,name in [('v1','baseline'),('v2','candidate'),('v3','recovered')]:
            prompt=load_prompt(root/f'prompts/{version}.yaml'); provider=ReplayProvider(root/f'fixtures/{name}.json',prompt)
            run=await evaluate(prompt,dataset,provider); store.add(run); runs.append(run)
            atomic_text(output/f'{name}-run.json',run.model_dump_json(indent=2)+'\n')
        baseline,candidate,recovered=runs
        results=[]
        for run,name in [(candidate,'regression'),(recovered,'recovery')]:
            result=compare(baseline,run,thresholds); history=store.history(run.dataset_hash)
            drift=slow_drift(history,run,thresholds); write_report(output/name,baseline,run,result,history,drift)
            atomic_text(output/name/'slack-payload.json',json.dumps(slack_payload(result,baseline,run),indent=2)+'\n'); results.append(result)
        # A separate controlled 7-run sequence tests slow drift without large drops.
        drift_runs=[]
        for i, failures in enumerate([0,0,1,1,2,2,3]):
            r=baseline.model_copy(deep=True); r.id='slow-drift-fixture-'+str(i); r.created_at=f'2026-11-03T00:0{i}:00+00:00'
            for index,c in enumerate(r.cases):
                c.category_correct=True; c.prediction=c.expected.model_copy(); c.passed=True
                if index<failures:
                    c.prediction.category='general' if c.expected.category!='general' else 'account'; c.category_correct=False; c.passed=False
            r.summary=summarize(r.cases); drift_runs.append(r)
        drift_thresholds=Thresholds(warn_drop=.07,critical_drop=.15,drift_floor=.93)
        step_statuses=[compare(a,b,drift_thresholds)['status'] for a,b in zip(drift_runs,drift_runs[1:])]
        if any(status!='pass' for status in step_statuses): raise GuardError('Slow-drift fixture unexpectedly triggered a per-run gate')
        drift=slow_drift(drift_runs[:-1],drift_runs[-1],drift_thresholds)
        atomic_text(output/'slow-drift-fixture.json',json.dumps({'provenance':'scripted system-test sequence; not live measurements','thresholds':drift_thresholds.model_dump(),'individual_step_statuses':step_statuses,'result':drift},indent=2)+'\n')
        summary={'provenance':'synthetic_fixture / recorded responses; no paid requests',
            'cases':len(dataset.cases),'baseline_pass_rate':baseline.summary['pass_rate'],
            'candidate_pass_rate':candidate.summary['pass_rate'],'regressions':len(results[0]['regressions']),
            'improvements':len(results[0]['improvements']),'gate':results[0]['status'],
            'recovered_pass_rate':recovered.summary['pass_rate'],'recovery_gate':results[1]['status'],
            'slow_drift_fixture':drift['status'],'slack_delivery':'not sent; payload saved',
            'report':str(output/'regression/report.html')}
        atomic_text(output/'demo.json',json.dumps(summary,indent=2)+'\n')
        return summary
    finally: store.close()
