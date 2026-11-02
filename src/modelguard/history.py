"""Persistent CI trend points contain aggregate measurements, never email text."""
from pathlib import Path
from pydantic import Field,field_validator
from typing import Literal
from .models import Strict,Run
from .config import read_json
from .reporting import atomic_text

class Point(Strict):
    id:str
    created_at:str
    dataset_hash:str
    provider:str
    judge_policy:str
    min_summary_score:int
    engine_version:str
    prompt_version:str
    pass_rate:float=Field(ge=0,le=1)
    errors:int=Field(ge=0)
    @field_validator('created_at')
    @classmethod
    def normalize_time(cls,value):return Run.valid_timestamp(value)
    @property
    def summary(self):return {'pass_rate':self.pass_rate,'errors':self.errors}

class Series(Strict):
    schema_version:Literal[1]=1
    points:list[Point]=Field(default_factory=list,max_length=1000)

def record_point(path:Path,run:Run):
    series=Series.model_validate(read_json(path)) if path.exists() else Series()
    point=Point(id=run.id,created_at=run.created_at,dataset_hash=run.dataset_hash,provider=run.provider,
        judge_policy=run.judge_policy,min_summary_score=run.min_summary_score,engine_version=run.engine_version,
        prompt_version=run.prompt_version,pass_rate=run.summary['pass_rate'],errors=run.summary['errors'])
    if any(p.id==point.id for p in series.points):raise ValueError('Duplicate history point')
    series.points=(series.points+[point])[-1000:]
    atomic_text(path,series.model_dump_json(indent=2)+'\n');return series

def point_drift(series:Series,current:Run,thresholds):
    compatible=[p for p in series.points if p.created_at<=current.created_at and all(getattr(p,k)==getattr(current,k)
        for k in ['dataset_hash','provider','judge_policy','min_summary_score','engine_version'])]
    window=sorted(compatible,key=lambda p:(p.created_at,p.id))[-thresholds.drift_window:]
    if any(p.errors for p in window):return {'status':'unavailable','reason':'Operational errors in trend window'}
    if len(window)<thresholds.drift_window:return {'status':'insufficient_history','runs':len(window),'required':thresholds.drift_window}
    average=sum(p.pass_rate for p in window)/len(window)
    return {'status':'warning' if average<thresholds.drift_floor else 'pass','runs':len(window),
        'moving_average':average,'floor':thresholds.drift_floor,'run_ids':[p.id for p in window]}
