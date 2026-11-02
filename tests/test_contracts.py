import json
from pathlib import Path
import tempfile
import unittest
from pydantic import ValidationError
from modelguard.models import Prediction, JudgeOutput
from modelguard.config import GuardError, load_prompt, read_json, Thresholds
from modelguard.dataset import load_dataset, dataset_hash
from helpers import ROOT

class Contracts(unittest.TestCase):
    def test_prediction_rejects_unknown_category(self):
        with self.assertRaises(ValidationError): Prediction(category='other',summary='A request.')
    def test_prediction_rejects_extra_keys(self):
        with self.assertRaises(ValidationError): Prediction(category='general',summary='A request.',secret='x')
    def test_summary_cannot_be_empty_or_multiline(self):
        for s in ['', '  ', 'one\ntwo']:
            with self.subTest(s=s),self.assertRaises(ValidationError): Prediction(category='general',summary=s)
    def test_judge_does_not_coerce_strings_or_bool_to_scores(self):
        for s in ['5',True,0,6]:
            with self.subTest(s=s),self.assertRaises(ValidationError): JudgeOutput(score=s,reason='Reason.')
    def test_prompt_hash_is_stable(self):
        self.assertEqual(load_prompt(ROOT/'prompts/v1.yaml').fingerprint,load_prompt(ROOT/'prompts/v1.yaml').fingerprint)
    def test_changed_prompt_hash_changes(self):
        self.assertNotEqual(load_prompt(ROOT/'prompts/v1.yaml').fingerprint,load_prompt(ROOT/'prompts/v2.yaml').fingerprint)
    def test_yaml_objects_aliases_duplicates_refused(self):
        for s in ['x: !!python/object:os.system {}', 'a: &loop [*loop]', 'version: one\nversion: two']:
            with tempfile.TemporaryDirectory() as td:
                p=Path(td)/'prompt.yaml';p.write_text(s)
                with self.assertRaises(Exception):load_prompt(p)
    def test_json_duplicate_and_nonfinite_refused(self):
        for s in ['{"id":1,"id":2}','{"x":NaN}']:
            with tempfile.TemporaryDirectory() as td:
                p=Path(td)/'data.json';p.write_text(s)
                with self.assertRaises(GuardError): read_json(p)
    def test_synthetic_dataset_not_gold(self):
        with self.assertRaises(GuardError):load_dataset(ROOT/'fixtures/dataset.json',require_gold=True)
    def test_empty_golden_template_intentionally_invalid(self):
        with self.assertRaises(ValidationError):load_dataset(ROOT/'data/golden.template.json',require_gold=True)
    def test_duplicates_not_additional_samples(self):
        data=json.loads((ROOT/'fixtures/dataset.json').read_text());data['cases'].append(data['cases'][0])
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'data.json';p.write_text(json.dumps(data))
            with self.assertRaises(GuardError):load_dataset(p)
    def test_duplicate_emails_with_different_ids_rejected(self):
        data=json.loads((ROOT/'fixtures/dataset.json').read_text());data['cases'].append({**data['cases'][0],'id':'another_id'})
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'data.json';p.write_text(json.dumps(data))
            with self.assertRaises(GuardError):load_dataset(p)
    def test_golden_requires_individual_review_metadata(self):
        data=json.loads((ROOT/'fixtures/dataset.json').read_text());data['provenance']='human_reviewed'
        # Dataset size itself must also be enough for the release protocol.
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'data.json';p.write_text(json.dumps(data))
            with self.assertRaises(GuardError):load_dataset(p,require_gold=True)
    def test_threshold_order_enforced(self):
        with self.assertRaises(GuardError): Thresholds(warn_drop=.1,critical_drop=.05).validate_order()
