"""Evaluate immutable Git data with a trusted engine; never install PR code."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import re
import subprocess
import json
from .config import GuardError,load_prompt,thresholds_from_env
from .dataset import load_dataset
from .providers import OpenAIProvider,Budget
from .runner import evaluate
from .comparison import compare,slow_drift
from .store import Store
from .reporting import write_report,atomic_text
from .notifications import slack_payload
from .history import record_point,point_drift


def read_blob(repository:Path,sha:str,path:str)->bytes:
    if not re.fullmatch(r'[a-f0-9]{40,64}',sha):raise GuardError('CI comparisons require immutable full commit SHAs')
    if not re.fullmatch(r'(prompts/[A-Za-z0-9_.-]+\.ya?ml|data/[A-Za-z0-9_.-]+\.json)',path):raise GuardError('CI file must be a direct prompt or dataset file')
    command=['git','--no-pager','show',sha+':'+path]
    size=subprocess.run(['git','cat-file','-s',sha+':'+path],cwd=repository,capture_output=True,timeout=20)
    if size.returncode:raise GuardError('Required prompt/golden data is absent from the selected Git commit')
    if int(size.stdout)>2_000_000:raise GuardError('Git input exceeds CI data budget')
    result=subprocess.run(command,cwd=repository,capture_output=True,timeout=20)
    if result.returncode:raise GuardError('Unable to read immutable Git input')
    return result.stdout

def select_prompt_paths(repository:Path,base:str,head:str,fallback:str):
    for sha in (base,head):
        if not re.fullmatch(r'[a-f0-9]{40,64}',sha):raise GuardError('Full immutable SHAs required')
    changed=subprocess.run(['git','diff','--no-ext-diff','--name-only',base,head,'--','prompts'],cwd=repository,capture_output=True,timeout=20)
    if changed.returncode:raise GuardError('Unable to discover changed prompt files')
    paths=[p for p in changed.stdout.decode().splitlines() if p.endswith(('.yaml','.yml'))]
    if len(paths)>1:raise GuardError('Multiple prompts changed; evaluate one candidate prompt per PR')
    candidate=paths[0] if paths else fallback
    if not re.fullmatch(r'prompts/[A-Za-z0-9_.-]+\.ya?ml',candidate):raise GuardError('Unsupported changed prompt path')
    exists=subprocess.run(['git','cat-file','-e',base+':'+candidate],cwd=repository,capture_output=True,timeout=20).returncode==0
    return (candidate if exists else fallback),candidate

def prerequisites(key:str,model:str,judge_model:str,enabled:bool)->list[str]:
    missing=[]
    if not enabled:missing.append('Live evaluation is not enabled by the repository owner')
    if not key:missing.append('OPENAI_API_KEY is not configured')
    if not model:missing.append('An explicit classifier model ID is not configured')
    if not judge_model:missing.append('An explicit judge model ID is not configured')
    return missing

async def evaluate_pair(repository:Path,base:str,head:str,prompt_path:str,dataset_path:str,output:Path,
                        model:str,judge_model:str,key:str,*,enabled:bool,max_requests:int=800,provider_factory=None):
    missing=prerequisites(key,model,judge_model,enabled)
    if missing:raise GuardError('; '.join(missing))
    base_path,candidate_path=select_prompt_paths(repository,base,head,prompt_path)
    base_prompt=read_blob(repository,base,base_path);head_prompt=read_blob(repository,head,candidate_path)
    raw_gold=read_blob(repository,base,dataset_path)
    if raw_gold!=read_blob(repository,head,dataset_path):raise GuardError('Golden dataset changed; review and freeze a new baseline separately')
    with TemporaryDirectory(prefix='modelguard-ci-inputs-') as folder:
        root=Path(folder);a=root/'base.yaml';b=root/'candidate.yaml';data=root/'gold.json'
        a.write_bytes(base_prompt);b.write_bytes(head_prompt);data.write_bytes(raw_gold)
        dataset=load_dataset(data,require_gold=True)
        if max_requests < len(dataset.cases)*8:raise GuardError('Shared request budget cannot cover both runs with bounded retries')
        budget=Budget(max_requests)
        factory=provider_factory or (lambda:OpenAIProvider(model,judge_model,key,budget=budget))
        baseline=await evaluate(load_prompt(a),dataset,factory())
        candidate=await evaluate(load_prompt(b),dataset,factory())
    output.mkdir(parents=True,exist_ok=True);store=Store(output/'history.sqlite')
    try:
        store.add(baseline);store.add(candidate);thresholds=thresholds_from_env()
        if baseline.summary['errors']:raise GuardError('Baseline provider/judge failed; no valid comparison is available')
        result=compare(baseline,candidate,thresholds)
        result['source']={'base_sha':base,'head_sha':head,'baseline_prompt':base_path,'candidate_prompt':candidate_path}
        series=record_point(output/'history-points.json',candidate)
        drift=point_drift(series,candidate,thresholds)
        if drift['status']=='warning' and result['status']=='pass':result['status']='warning'
        result['drift']=drift
        write_report(output,baseline,candidate,result,series.points,drift)
        atomic_text(output/'slack-payload.json',json.dumps(slack_payload(result,baseline,candidate,os.environ.get('MODELGUARD_REPORT_URL')),indent=2)+'\n')
        return result
    finally:store.close()

def gate_summary(result:dict|None,reason:str|None=None)->str:
    if result is None:
        return '## ModelGuard: blocked\n\nLive quality evaluation did not run.\n\n'+(reason or 'Check the run logs and setup requirements.')+'\n\nThis is not a passing quality result.\n'
    return f"## ModelGuard: {result['status']}\n\nPass-rate delta: {100*result['delta']:+.2f} pp.\n\n{len(result['regressions'])} regressions; {len(result['improvements'])} improvements.\n\nPaired exact p-value: {result['mcnemar_exact_p']:.4f}. Practical thresholds are separate from statistical significance.\n"
