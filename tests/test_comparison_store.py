import tempfile
from pathlib import Path
import unittest
from modelguard.models import Prediction
from modelguard.scoring import summarize
from modelguard.comparison import compare, slow_drift, validate_run
from modelguard.statistics import exact_mcnemar, percentile, wilson
from modelguard.config import Thresholds, GuardError
from modelguard.store import Store
from helpers import make_run

class Comparisons(unittest.TestCase):
    def setUp(self):self.b=make_run();self.c=make_run('candidate','v2')
    def test_specific_regressions_and_improvements(self):
        c=compare(self.b,self.c,Thresholds());self.assertEqual(c['status'],'critical');self.assertEqual(len(c['regressions']),4);self.assertEqual(len(c['improvements']),1);self.assertAlmostEqual(c['delta'],-.1875)
    def test_reordering_cases_does_not_change_pairing(self):
        self.c.cases.reverse();a=compare(self.b,self.c,Thresholds());self.assertEqual(len(a['regressions']),4)
    def test_changed_dataset_identity_not_comparable(self):
        self.c.dataset_hash='changed'
        with self.assertRaises(GuardError):compare(self.b,self.c,Thresholds())
    def test_changed_case_content_not_comparable(self):
        self.c.case_hashes['bill_duplicate']='changed'
        with self.assertRaises(GuardError):compare(self.b,self.c,Thresholds())
    def test_different_expected_labels_cannot_hide_behind_same_dataset_hash(self):
        self.c.cases[0].expected.summary='A different reference summary.'
        with self.assertRaises(GuardError):compare(self.b,self.c,Thresholds())
    def test_changed_judge_cannot_masquerade_as_model_delta(self):
        self.c.judge_policy='new'
        with self.assertRaises(GuardError):compare(self.b,self.c,Thresholds())
    def test_operational_failures_are_not_quality_only_failures(self):
        self.c.cases[0].error='provider_network_error';self.c.cases[0].passed=False;self.c.summary=summarize(self.c.cases)
        self.assertEqual(compare(self.b,self.c,Thresholds())['status'],'error')
    def test_forged_summary_rejected(self):
        self.c.summary['pass_rate']=1
        with self.assertRaises(GuardError):compare(self.b,self.c,Thresholds())
    def test_threshold_is_not_claimed_statistical_significance(self):
        c=compare(self.b,self.c,Thresholds());self.assertGreater(c['mcnemar_exact_p'],.05);self.assertEqual(c['status'],'critical')
    def test_recovery_passes(self):
        r=make_run('recovered','v3');self.assertEqual(compare(self.b,r,Thresholds())['status'],'pass')
    def test_insufficient_drift_history_is_not_pass(self):
        self.assertEqual(slow_drift([],self.c,Thresholds())['status'],'insufficient_history')
    def test_drift_does_not_look_into_the_future(self):
        later=self.b.model_copy(deep=True);later.created_at='2099-01-01T00:00:00+00:00'
        self.assertEqual(slow_drift([later],self.c,Thresholds())['runs'],1)
    def test_drift_uses_exact_window(self):
        history=[]
        for i in range(7):
            r=self.b.model_copy(deep=True);r.id=str(i);r.created_at=f'2026-01-01T00:0{i}:00+00:00';history.append(r)
        d=slow_drift(history[:-1],history[-1],Thresholds(drift_floor=.9));self.assertEqual(d['status'],'warning');self.assertEqual(d['runs'],7)
    def test_synthetic_recordings_are_not_release_evidence(self):
        self.assertFalse(compare(self.b,self.c,Thresholds())['release_evidence'])

class Storage(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name)/'runs.sqlite');self.r=make_run();self.s.add(self.r)
    def tearDown(self):self.s.close();self.tmp.cleanup()
    def test_roundtrip(self):self.assertEqual(self.s.get(self.r.id).model_dump(),self.r.model_dump())
    def test_runs_are_immutable(self):
        with self.assertRaises(GuardError):self.s.add(self.r)
    def test_missing_run_fails(self):
        with self.assertRaises(GuardError):self.s.get('missing')
    def test_sql_injection_is_just_a_missing_id(self):
        with self.assertRaises(GuardError):self.s.get("' OR 1=1 --")
        self.assertEqual(len(self.s.history(self.r.dataset_hash)),1)
    def test_synthetic_run_cannot_be_production_baseline(self):
        with self.assertRaises(GuardError):self.s.promote('production',self.r.id)
    def test_explicit_fixture_baseline_can_be_used_in_system_tests(self):
        self.s.promote('fixture',self.r.id,allow_fixture=True);self.assertEqual(self.s.baseline('fixture').id,self.r.id)

class Stats(unittest.TestCase):
    def test_mcnemar_no_changes(self):self.assertEqual(exact_mcnemar(0,0),1)
    def test_mcnemar_known_exact_result(self):self.assertEqual(exact_mcnemar(5,0),.0625)
    def test_symmetric_mcnemar(self):self.assertEqual(exact_mcnemar(4,1),exact_mcnemar(1,4))
    def test_percentiles_and_missing_data(self):self.assertIsNone(percentile([],.95));self.assertEqual(percentile([2,1,4,3],.95),4)
    def test_perfect_small_sample_has_uncertainty(self):
        lo,hi=wilson(8,8);self.assertLess(lo,.7);self.assertAlmostEqual(hi,1)
