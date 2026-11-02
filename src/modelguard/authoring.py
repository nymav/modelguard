"""Human authoring and review workflow. No AI-generated gold or bulk auto-approval."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import io
import json
from typing import Literal
from pydantic import Field
from .models import Strict, Case, Dataset
from .dataset import validate_dataset, reviewed_content_hash
from .config import GuardError, read_json
from .reporting import atomic_text

COLUMNS=['id','email','category','ideal_summary','difficulty','notes']
class ReviewQueue(Strict):
    schema_version: Literal[1] = 1
    kind: Literal['human_authored_review_queue'] = 'human_authored_review_queue'
    version: str = Field(min_length=1,max_length=100)
    authorship_declaration: str = 'Submitter declares original human-authored or lawfully sourced data; not independently verified.'
    cases: list[Case] = Field(min_length=1,max_length=100)

def authoring_template(path: Path, count: int=64):
    if path.exists(): raise GuardError('Refusing to overwrite an existing authoring file')
    if not 50<=count<=100: raise GuardError('Choose 50–100 authoring rows')
    stream=io.StringIO(newline=''); writer=csv.DictWriter(stream,fieldnames=COLUMNS);writer.writeheader()
    for i in range(count):writer.writerow(dict(id=f'case_{i+1:03d}',email='',category='',ideal_summary='',difficulty='normal',notes=''))
    atomic_text(path,stream.getvalue())

def import_authoring(path: Path, output: Path, version: str, declared_human: bool):
    if not declared_human: raise GuardError('Explicit human-authorship declaration is required; do not relabel synthetic fixtures')
    if output.exists():raise GuardError('Refusing to overwrite an existing review queue')
    if path.stat().st_size>2_000_000:raise GuardError('Authoring CSV exceeds size limit')
    with path.open(newline='',encoding='utf-8-sig') as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames!=COLUMNS:raise GuardError('Unexpected authoring columns; use dataset-template')
        cases=[]
        for row in reader:
            if any(v is None or not isinstance(v,str) for v in row.values()):raise GuardError('Malformed CSV row')
            if not any(row[k].strip() for k in ['email','category','ideal_summary','notes']):continue
            cases.append(Case(id=row['id'],email=row['email'],expected={'category':row['category'],'summary':row['ideal_summary']},difficulty=row['difficulty'],notes=row['notes']))
    queue=ReviewQueue(version=version,cases=cases)
    validate_dataset(Dataset(schema_version=1,version=version,provenance='synthetic_fixture',description='Validation-only temporary envelope; not saved as fixture data.',cases=cases))
    atomic_text(output,queue.model_dump_json(indent=2)+'\n');return queue

def approve_case(case: Case, reviewer: str, decision: str) -> Case:
    if decision!='approve':raise GuardError('Approval requires the exact decision approve')
    if not reviewer.strip() or len(reviewer)>200:raise GuardError('Provide the actual human reviewer name')
    result=case.model_copy(deep=True);result.reviewed_by=reviewer.strip()
    result.reviewed_at=datetime.now(timezone.utc).isoformat();result.reviewed_content_hash=reviewed_content_hash(result)
    return result

def review_queue(path: Path, reviewer: str, *, input_fn=input, output_fn=print):
    queue=ReviewQueue.model_validate(read_json(path))
    for i,case in enumerate(queue.cases):
        if case.reviewed_content_hash==reviewed_content_hash(case) and case.reviewed_by and case.reviewed_at:continue
        output_fn(f'Case {i+1}/{len(queue.cases)} — verify authorship, category, summary and rationale.')
        # JSON string escaping keeps untrusted email control sequences out of the terminal.
        output_fn(json.dumps(case.model_dump(exclude={'reviewed_by','reviewed_at','reviewed_content_hash'}),indent=2,ensure_ascii=False))
        decision=input_fn('Personally checked? Type approve, skip or quit: ').strip().lower()
        if decision=='quit':break
        if decision=='skip':continue
        if decision!='approve':raise GuardError('Unrecognized decision; no approval was recorded for this case')
        queue.cases[i]=approve_case(case,reviewer,decision)
        atomic_text(path,queue.model_dump_json(indent=2)+'\n')
    return queue

def export_gold(path: Path, output: Path):
    if output.exists():raise GuardError('Refusing to overwrite a frozen golden dataset; choose a new version/file')
    queue=ReviewQueue.model_validate(read_json(path))
    data=Dataset(schema_version=1,version=queue.version,provenance='human_reviewed',
        description='Human-authored data with individual content-bound review declarations. Review identity is not independently verified.',cases=queue.cases)
    validate_dataset(data,require_gold=True)
    atomic_text(output,data.model_dump_json(indent=2)+'\n');return data
