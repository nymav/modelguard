"""Load bounded YAML data, never objects, templates or Python expressions."""
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import yaml
from pydantic import Field
from .models import Strict, Prediction

class GuardError(ValueError):
    pass

def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()

def read_json(path: Path, max_bytes: int = 10_000_000):
    if path.stat().st_size > max_bytes:
        raise GuardError('Input exceeds size limit')
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result: raise GuardError('Duplicate JSON key')
            result[k] = v
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(GuardError('Nonfinite JSON number')))

class FewShot(Strict):
    email: str = Field(min_length=1, max_length=12000)
    output: Prediction

class PromptDocument(Strict):
    version: str = Field(min_length=1, max_length=100)
    timestamp: str
    system_prompt: str = Field(min_length=1, max_length=24000)
    few_shot: list[FewShot] = Field(default_factory=list, max_length=20)
    max_output_tokens: int = Field(default=500, ge=100, le=4000)

@dataclass(frozen=True)
class PromptConfig:
    version: str
    timestamp: str
    system_prompt: str
    few_shot: tuple[FewShot, ...]
    max_output_tokens: int
    fingerprint: str

def load_prompt(path: Path) -> PromptConfig:
    if path.stat().st_size > 100000: raise GuardError('Prompt file too large')
    # Reject aliases to prevent recursive structures and expansion surprises.
    value = path.read_text()
    for token in yaml.scan(value):
        if isinstance(token, (yaml.AliasToken, yaml.AnchorToken)):
            raise GuardError('YAML anchors and aliases are not supported')
    class UniqueLoader(yaml.SafeLoader): pass
    def unique(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result: raise GuardError('Duplicate or non-string YAML key')
            result[key] = loader.construct_object(value_node, deep=deep)
        return result
    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique)
    doc = PromptDocument.model_validate(yaml.load(value, Loader=UniqueLoader))
    stamp = datetime.fromisoformat(doc.timestamp.replace('Z', '+00:00'))
    if stamp.tzinfo is None: raise GuardError('Prompt timestamp must include a timezone')
    return PromptConfig(doc.version, doc.timestamp, doc.system_prompt, tuple(doc.few_shot), doc.max_output_tokens, digest(doc.model_dump()))

class Thresholds(Strict):
    warn_drop: float = Field(default=0.03, gt=0, le=1)
    critical_drop: float = Field(default=0.08, gt=0, le=1)
    drift_window: int = Field(default=7, ge=2, le=100)
    drift_floor: float = Field(default=0.90, ge=0, le=1)
    def validate_order(self):
        if self.warn_drop >= self.critical_drop: raise GuardError('Warning threshold must be below critical threshold')
        return self

def thresholds_from_env() -> Thresholds:
    values = {}
    for key in ['warn_drop', 'critical_drop', 'drift_floor']:
        if 'MODELGUARD_' + key.upper() in os.environ:
            values[key] = float(os.environ['MODELGUARD_' + key.upper()])
    return Thresholds(**values).validate_order()
