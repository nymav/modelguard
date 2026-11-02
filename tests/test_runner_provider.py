import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from modelguard.config import GuardError, load_prompt, FewShot
from dataclasses import replace
from modelguard.dataset import load_dataset
from modelguard.models import Observation, Prediction
from modelguard.providers import Budget, ProviderFailure, OpenAIProvider, ReplayProvider
from modelguard.runner import evaluate
from modelguard.feature import classify_email
from helpers import ROOT, make_run

class FakeProvider:
    mode='replay';model='test';fingerprint='test';judge_policy='test-rubric'
    def __init__(self, raw=None, judge=None, fail=False):
        self.raw=raw;self.rating=judge;self.fail=fail
        self.labels={c.id:c.expected for c in load_dataset(ROOT/'fixtures/dataset.json').cases}
    async def classify(self,prompt,case):
        if self.fail:raise ProviderFailure('provider_network_error')
        return Observation(raw=self.raw if self.raw is not None else self.labels[case.id].model_dump_json())
    async def judge(self,case,prediction):return Observation(raw=self.rating or '{"score":5,"reason":"Relevant."}')

def response(raw='{"category":"billing","summary":"A refund request."}', **kwargs):
    return {'id':'test-response','status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':raw}]}],**kwargs}

class Runner(unittest.TestCase):
    def setUp(self):self.p=load_prompt(ROOT/'prompts/v1.yaml');self.d=load_dataset(ROOT/'fixtures/dataset.json')
    def run_eval(self,provider,**kwargs):return asyncio.run(evaluate(self.p,self.d,provider,**kwargs))
    def test_feature_accepts_email_without_gold_label(self):
        provider=ReplayProvider(ROOT/'fixtures/baseline.json',self.p)
        prediction,observation=asyncio.run(classify_email(self.d.cases[0].email,self.p,provider,case_id=self.d.cases[0].id))
        self.assertEqual(prediction.category,'billing');self.assertIsNone(observation.elapsed_ms)
    def test_invalid_prediction_preserves_raw_evidence(self):
        r=self.run_eval(FakeProvider(raw='not JSON'))
        self.assertEqual(r.cases[0].raw,'not JSON');self.assertEqual(r.cases[0].error,'invalid_prediction')
    def test_perfect_fixture_passes_all_cases(self):
        r=self.run_eval(FakeProvider());self.assertEqual(r.summary['pass_rate'],1);self.assertEqual(len(r.cases),16)
    def test_invalid_outputs_are_errors_not_silently_dropped(self):
        r=self.run_eval(FakeProvider(raw='not JSON'));self.assertEqual(r.summary['errors'],16);self.assertEqual(r.summary['pass_rate'],0)
    def test_judge_failures_not_perfect_scores(self):
        r=self.run_eval(FakeProvider(judge='{"score":99,"reason":"bad"}'));self.assertEqual(r.summary['errors'],16);self.assertIsNone(r.summary['summary_mean'])
    def test_relevance_failure_can_fail_correct_category(self):
        r=self.run_eval(FakeProvider(judge='{"score":1,"reason":"Unrelated summary."}'))
        self.assertEqual(r.summary['category_accuracy'],1);self.assertEqual(r.summary['pass_rate'],0)
    def test_explicit_category_only_skips_judge(self):
        r=self.run_eval(FakeProvider(judge='invalid'),category_only=True);self.assertEqual(r.judge_policy,'category_only');self.assertEqual(r.summary['pass_rate'],1)
    def test_network_failure_is_retained_per_case(self):
        r=self.run_eval(FakeProvider(fail=True));self.assertEqual(r.summary['errors'],16)
    def test_replay_has_no_fabricated_measurements(self):
        r=make_run();self.assertIsNone(r.summary['classification_p95_ms']);self.assertIsNone(r.summary['input_tokens']);self.assertFalse(r.summary['usage_complete'])
    def test_concurrency_is_actually_bounded(self):
        class Measured(FakeProvider):
            active=0;maximum=0
            async def classify(self,p,c):
                self.active+=1;self.maximum=max(self.maximum,self.active);await asyncio.sleep(.001)
                self.active-=1;return await super().classify(p,c)
        provider=Measured();self.run_eval(provider,concurrency=3);self.assertEqual(provider.maximum,3)
    def test_gold_input_in_few_shot_examples_is_rejected(self):
        sample=self.d.cases[0]
        p=replace(self.p,few_shot=(FewShot(email=sample.email,output=sample.expected),))
        with self.assertRaises(GuardError):asyncio.run(evaluate(p,self.d,FakeProvider()))
    def test_invalid_concurrency_refused(self):
        with self.assertRaises(GuardError):self.run_eval(FakeProvider(),concurrency=0)
    def test_recording_binds_to_prompt(self):
        with self.assertRaises(GuardError):ReplayProvider(ROOT/'fixtures/baseline.json',load_prompt(ROOT/'prompts/v2.yaml'))
    def test_recording_binds_to_email(self):
        d=self.d.model_copy(deep=True);d.cases[0].email='Changed input'
        r=asyncio.run(evaluate(self.p,d,ReplayProvider(ROOT/'fixtures/baseline.json',self.p)))
        self.assertEqual(r.summary['errors'],1)

class OpenAIAdapter(unittest.TestCase):
    def provider(self,transport,**kwargs): return OpenAIProvider('explicit-model','judge-model','test-key-never-real',budget=Budget(20),transport=transport,**kwargs)
    def call(self,p):return p._call(p.model,[],{},'test',500)
    def test_structured_responses_request_and_usage(self):
        sent=[]
        def transport(url,key,payload,timeout):sent.append(payload);return response(usage={'input_tokens':12,'output_tokens':8})
        obs=self.call(self.provider(transport));self.assertEqual(obs.usage.input_tokens,12);self.assertEqual(obs.attempts,1)
        self.assertFalse(sent[0]['store']);self.assertTrue(sent[0]['text']['format']['strict'])
    def test_refusal_is_not_parsed_as_prediction(self):
        p=self.provider(lambda *args:{'status':'completed','output':[{'type':'message','content':[{'type':'refusal','refusal':'No'}]}]})
        with self.assertRaisesRegex(ProviderFailure,'provider_refusal'):self.call(p)
    def test_incomplete_output_is_operational_error(self):
        with self.assertRaisesRegex(ProviderFailure,'provider_incomplete'):self.call(self.provider(lambda *args:{'status':'incomplete'}))
    def test_retry_transient_failure_is_bounded_and_counted(self):
        calls=[]
        def transport(*args):
            calls.append(1)
            if len(calls)==1:raise ProviderFailure('provider_http_429')
            return response()
        obs=self.call(self.provider(transport));self.assertEqual(len(calls),2);self.assertEqual(obs.attempts,2)
    def test_auth_failure_is_not_retried(self):
        calls=[]
        def transport(*args):calls.append(1);raise ProviderFailure('provider_http_401')
        with self.assertRaises(ProviderFailure):self.call(self.provider(transport))
        self.assertEqual(len(calls),1)
    def test_budget_is_a_hard_limit(self):
        budget=Budget(1);budget.reserve()
        with self.assertRaisesRegex(ProviderFailure,'budget_exhausted'):budget.reserve()
    def test_budget_exhaustion_never_calls_transport(self):
        calls=[];p=self.provider(lambda *args:calls.append(1));p.budget=Budget(1);p.budget.reserve()
        with self.assertRaisesRegex(ProviderFailure,'budget_exhausted'):self.call(p)
        self.assertEqual(calls,[])
    def test_missing_key_refused(self):
        with self.assertRaises(GuardError):OpenAIProvider('explicit-model',None,'',budget=Budget(1))
