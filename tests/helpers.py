from pathlib import Path
import asyncio
from modelguard.config import load_prompt
from modelguard.dataset import load_dataset
from modelguard.providers import ReplayProvider
from modelguard.runner import evaluate
ROOT=Path(__file__).resolve().parents[1]
def make_run(name='baseline', version='v1', **kwargs):
    p=load_prompt(ROOT/f'prompts/{version}.yaml'); d=load_dataset(ROOT/'fixtures/dataset.json')
    return asyncio.run(evaluate(p,d,ReplayProvider(ROOT/f'fixtures/{name}.json',p),**kwargs))
