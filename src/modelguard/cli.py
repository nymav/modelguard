"""Explicit replay/live commands. CI exit 2 blocks critical regressions; 3 is error."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sqlite3
from pydantic import ValidationError
import yaml
from . import __version__
from .config import GuardError, load_prompt, thresholds_from_env, read_json
from .dataset import load_dataset
from .providers import ReplayProvider, OpenAIProvider, Budget
from .runner import evaluate
from .store import Store
from .comparison import compare, slow_drift
from .reporting import atomic_text, write_report
from .notifications import slack_payload, send_slack


def parser():
    p=argparse.ArgumentParser(prog='modelguard',description='Compare LLM behavior using paired case evidence')
    p.add_argument('--version',action='version',version=__version__)
    sub=p.add_subparsers(dest='command',required=True)
    demo=sub.add_parser('demo'); demo.add_argument('--output',type=Path,default=Path('artifacts/demo'))
    for name in ['replay','live']:
        run=sub.add_parser(name); run.add_argument('--prompt',type=Path,required=True); run.add_argument('--dataset',type=Path,required=True)
        run.add_argument('--db',type=Path,default=Path('.run/modelguard.sqlite')); run.add_argument('--output',type=Path,default=Path('.run/latest'))
        run.add_argument('--concurrency',type=int,default=4); run.add_argument('--min-summary-score',type=int,default=3)
        run.add_argument('--category-only',action='store_true',help='Explicitly skip summary judging; changes scoring identity')
        if name=='replay': run.add_argument('--recording',type=Path,required=True)
        else:
            run.add_argument('--model',required=True); run.add_argument('--judge-model'); run.add_argument('--max-requests',type=int,default=400)
            run.add_argument('--max-cases',type=int,default=100); run.add_argument('--allow-live',action='store_true',help='Authorize paid requests and transmit dataset emails to OpenAI')
    comp=sub.add_parser('compare'); group=comp.add_mutually_exclusive_group(required=True); group.add_argument('--baseline'); group.add_argument('--baseline-name'); comp.add_argument('--candidate',required=True)
    comp.add_argument('--db',type=Path,default=Path('.run/modelguard.sqlite')); comp.add_argument('--output',type=Path,default=Path('.run/comparison'))
    history=sub.add_parser('history'); history.add_argument('--db',type=Path,default=Path('.run/modelguard.sqlite')); history.add_argument('--run',required=True)
    base=sub.add_parser('baseline'); base.add_argument('--db',type=Path,default=Path('.run/modelguard.sqlite')); base.add_argument('--run',required=True); base.add_argument('--name',default='production')
    check=sub.add_parser('validate-dataset'); check.add_argument('path',type=Path); check.add_argument('--require-gold',action='store_true')
    notify=sub.add_parser('notify'); notify.add_argument('--payload',type=Path,required=True); notify.add_argument('--send-slack',action='store_true')
    return p

def emit(value): print(json.dumps(value,allow_nan=False))

def main(argv=None):
    args=parser().parse_args(argv); store=None
    try:
        if args.command=='demo':
            from .demo import demo
            emit(asyncio.run(demo(args.output))); return 0
        if args.command=='validate-dataset':
            d=load_dataset(args.path,require_gold=args.require_gold); emit({'valid':True,'cases':len(d.cases),'provenance':d.provenance}); return 0
        if args.command=='notify':
            payload=read_json(args.payload)
            if args.send_slack:
                send_slack(os.environ.get('SLACK_WEBHOOK_URL',''),payload); emit({'delivered':True})
            else: emit({'delivery':'dry_run','payload':payload})
            return 0
        store=Store(args.db)
        if args.command in ['replay','live']:
            prompt=load_prompt(args.prompt); dataset=load_dataset(args.dataset,require_gold=args.command=='live')
            if args.command=='live':
                if not args.allow_live: raise GuardError('Live requests require --allow-live')
                if not args.category_only and not args.judge_model: raise GuardError('Specify --judge-model or explicitly use --category-only')
                if not 1<=args.max_cases<=100 or len(dataset.cases)>args.max_cases: raise GuardError('Dataset exceeds explicit case budget')
                expected=len(dataset.cases)*(1 if args.category_only else 2)*2
                if args.max_requests<expected: raise GuardError('Request budget must cover bounded retries for every case and judge')
                provider=OpenAIProvider(args.model,args.judge_model,os.environ.get('OPENAI_API_KEY',''),budget=Budget(args.max_requests))
            else: provider=ReplayProvider(args.recording,prompt)
            run=asyncio.run(evaluate(prompt,dataset,provider,concurrency=args.concurrency,min_summary_score=args.min_summary_score,category_only=args.category_only))
            store.add(run); atomic_text(args.output/'run.json',run.model_dump_json(indent=2)+'\n')
            emit({'run_id':run.id,'provider':run.provider,'provenance':run.provenance,**run.summary})
            return 3 if run.summary['errors'] else 0
        if args.command=='compare':
            baseline=store.get(args.baseline) if args.baseline else store.baseline(args.baseline_name); candidate=store.get(args.candidate); thresholds=thresholds_from_env()
            comparison=compare(baseline,candidate,thresholds); history=store.history(candidate.dataset_hash)
            drift=slow_drift(history,candidate,thresholds); write_report(args.output,baseline,candidate,comparison,history,drift)
            payload=slack_payload(comparison,baseline,candidate,os.environ.get('MODELGUARD_REPORT_URL'))
            atomic_text(args.output/'slack-payload.json',json.dumps(payload,indent=2)+'\n')
            emit({'comparison':comparison,'drift':drift,'report':str(args.output/'report.html')})
            return 3 if comparison['status']=='error' else 2 if comparison['status']=='critical' else 0
        if args.command=='history':
            run=store.get(args.run); emit([{'id':r.id,'prompt_version':r.prompt_version,'pass_rate':r.summary['pass_rate']} for r in store.history(run.dataset_hash)]); return 0
        if args.command=='baseline': store.promote(args.name,args.run); emit({'baseline':args.name,'run_id':args.run}); return 0
    except (GuardError,ValidationError,OSError,ValueError,TypeError,KeyError,sqlite3.Error,yaml.YAMLError) as error:
        # Validation detail can echo raw email data; report only its error class.
        emit({'error':str(error) if isinstance(error,GuardError) else type(error).__name__,'exit_code':3}); return 3
    finally:
        if store: store.close()
    return 3

if __name__=='__main__': raise SystemExit(main())
