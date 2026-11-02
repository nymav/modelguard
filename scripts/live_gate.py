"""Environment-only CI entrypoint, run from the trusted engine checkout."""
import asyncio
import json
import os
from pathlib import Path
import sys
from modelguard.ci import evaluate_pair,gate_summary,prerequisites
from modelguard.config import GuardError
from modelguard.reporting import atomic_text
from modelguard.github import GitHubSummary

output=Path(os.environ.get('MODELGUARD_OUTPUT','artifacts/live-evaluation'));result=None;reason=None
try:
    missing=prerequisites(os.environ.get('OPENAI_API_KEY',''),os.environ.get('MODEL_ID',''),os.environ.get('JUDGE_MODEL_ID',''),os.environ.get('MODELGUARD_LIVE_ENABLED')=='true')
    if missing:raise GuardError('; '.join(missing))
    result=asyncio.run(evaluate_pair(Path(os.environ['TARGET_REPOSITORY']),os.environ['BASE_SHA'],os.environ['HEAD_SHA'],
        os.environ.get('PROMPT_PATH','prompts/v1.yaml'),'data/golden.json',output,
        os.environ.get('MODEL_ID',''),os.environ.get('JUDGE_MODEL_ID',''),os.environ.get('OPENAI_API_KEY',''),
        enabled=os.environ.get('MODELGUARD_LIVE_ENABLED')=='true'))
except GuardError as error:reason=str(error)
except Exception as error:reason='Evaluation failed: '+type(error).__name__
body=gate_summary(result,reason)
link=os.environ.get('MODELGUARD_REPORT_URL')
if link and link.startswith('https://github.com/'):body+='\nRun and report artifacts: '+link+'\n'
atomic_text(output/'summary.md',body)
status=result['status'] if result else 'blocked'
atomic_text(output/'gate-status.json',json.dumps({'status':status,'reason':reason,'result':result},indent=2)+'\n')
if os.environ.get('GITHUB_STEP_SUMMARY'):
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write(body)
if os.environ.get('MODELGUARD_POST_COMMENT')=='true' and os.environ.get('PR_NUMBER'):
    try:GitHubSummary(os.environ['GITHUB_REPOSITORY'],os.environ['GITHUB_TOKEN']).publish(int(os.environ['PR_NUMBER']),body,os.environ['HEAD_SHA'])
    except Exception as error:
        atomic_text(output/'comment-error.txt','PR summary delivery failed: '+type(error).__name__+'\n')
        print('PR summary delivery failed; inspect artifact.');sys.exit(3)
print(json.dumps({'status':status,'reason':reason}))
raise SystemExit(3 if status in ['blocked','error'] else 2 if status=='critical' else 0)
