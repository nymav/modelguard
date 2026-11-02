"""Dataset identity and provenance gates; synthetic fixtures cannot become gold."""
from datetime import datetime
from pathlib import Path
from .models import Dataset
from .config import GuardError, digest, read_json

def reviewed_content_hash(case) -> str:
    return digest(case.model_dump(exclude={"reviewed_by", "reviewed_at", "reviewed_content_hash"}))

def validate_dataset(data: Dataset, *, require_gold: bool = False) -> Dataset:
    ids = [c.id for c in data.cases]
    if len(set(ids)) != len(ids): raise GuardError('Duplicate case IDs')
    normalized = [' '.join(c.email.lower().split()) for c in data.cases]
    if len(set(normalized)) != len(normalized): raise GuardError('Duplicate email inputs inflate evaluation sample size')
    if require_gold:
        if data.provenance != 'human_reviewed': raise GuardError('Release evaluation requires human-reviewed ground truth')
        if not 50 <= len(data.cases) <= 100:
            raise GuardError('Release golden dataset must contain 50–100 reviewed cases')
        if {c.expected.category for c in data.cases} != {'billing', 'technical', 'account', 'general'}:
            raise GuardError('Golden dataset must cover all four categories')
        for c in data.cases:
            if not c.reviewed_by or not c.reviewed_by.strip() or not c.reviewed_at:
                raise GuardError('Each golden case requires a human reviewer and date')
            date = datetime.fromisoformat(c.reviewed_at.replace('Z', '+00:00'))
            if date.tzinfo is None: raise GuardError('Review timestamp must include timezone')
            if c.reviewed_content_hash != reviewed_content_hash(c):
                raise GuardError('Case content changed after review or content-bound approval is missing')
    return data

def load_dataset(path: Path, *, require_gold: bool = False) -> Dataset:
    return validate_dataset(Dataset.model_validate(read_json(path)), require_gold=require_gold)

def dataset_hash(dataset: Dataset) -> str:
    return digest(dataset.model_dump())

def case_hashes(dataset: Dataset) -> dict[str, str]:
    return {c.id: digest(c.model_dump()) for c in dataset.cases}
