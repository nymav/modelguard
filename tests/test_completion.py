"""Contract tests use synthetic test objects; they create no real approved gold."""
import asyncio
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from modelguard.authoring import authoring_template,import_authoring,approve_case,ReviewQueue,export_gold,review_queue
from modelguard.dataset import reviewed_content_hash,load_dataset
from modelguard.config import GuardError,Thresholds
from modelguard.ci import prerequisites,gate_summary,read_blob,evaluate_pair
from modelguard.github import GitHubSummary,MARKER
from modelguard.history import record_point,point_drift
from helpers import make_run,ROOT

class Authoring(unittest.TestCase):
    def test_template_is_blank_and_does_not_approve_anything(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'author.csv';authoring_template(p)
            rows=list(csv.DictReader(io.StringIO(p.read_text())));self.assertEqual(len(rows),64);self.assertTrue(all(not r['email'] for r in rows))
            with self.assertRaises(GuardError):authoring_template(p)
    def test_import_requires_explicit_authorship_declaration(self):
        with self.assertRaises(GuardError):import_authoring(Path('missing'),Path('unused'),'v1',False)
    def test_approval_binds_to_content(self):
        case=load_dataset(ROOT/'fixtures/dataset.json').cases[0]
        approved=approve_case(case,'UNIT TEST REVIEWER','approve')
        self.assertEqual(approved.reviewed_content_hash,reviewed_content_hash(approved))
        approved.expected.summary='Different text.'
        self.assertNotEqual(approved.reviewed_content_hash,reviewed_content_hash(approved))
    def test_no_bulk_or_implicit_approval(self):
        case=load_dataset(ROOT/'fixtures/dataset.json').cases[0]
        with self.assertRaises(GuardError):approve_case(case,'unit-test','yes')
    def test_skip_does_not_mark_reviewed(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'queue.json';q=ReviewQueue(version='unit-test',cases=load_dataset(ROOT/'fixtures/dataset.json').cases[:1]);path.write_text(q.model_dump_json())
            result=review_queue(path,'UNIT TEST',input_fn=lambda _: 'skip',output_fn=lambda _: None)
            self.assertIsNone(result.cases[0].reviewed_by)
    def test_incomplete_queue_cannot_freeze_as_gold(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'q.json';p.write_text(ReviewQueue(version='unit-test',cases=load_dataset(ROOT/'fixtures/dataset.json').cases).model_dump_json())
            with self.assertRaises(GuardError):export_gold(p,Path(td)/'gold.json')
            self.assertFalse((Path(td)/'gold.json').exists())

class GithubComments(unittest.TestCase):
    def api(self,comments=None,head=None,fork=False):
        calls=[]
        def transport(method,path,payload=None):
            calls.append((method,path,payload))
            if '/pulls/' in path:return {'state':'open','head':{'sha':head or 'a'*40,'repo':{'full_name':'fork/repo' if fork else 'owner/repo'}}}
            if method=='GET':return comments or []
            return {'id':99}
        return GitHubSummary('owner/repo','test-not-real',transport=transport),calls
    def test_creates_one_bot_summary(self):
        api,calls=self.api();result=api.publish(1,'Ready','a'*40);self.assertFalse(result['updated']);self.assertEqual(calls[-1][0],'POST')
    def test_upserts_only_bot_owned_marker(self):
        comments=[{'id':1,'body':MARKER,'user':{'type':'User','login':'somebody'}},{'id':2,'body':MARKER,'user':{'type':'Bot','login':'github-actions[bot]'}}]
        api,calls=self.api(comments);self.assertTrue(api.publish(1,'Updated','a'*40)['updated']);self.assertEqual(calls[-1][1],'/repos/owner/repo/issues/comments/2')
    def test_stale_head_refused_without_write(self):
        api,calls=self.api(head='b'*40)
        with self.assertRaises(GuardError):api.publish(1,'Stale','a'*40)
        self.assertTrue(all(c[0]=='GET' for c in calls))
    def test_fork_refused(self):
        api,calls=self.api(fork=True)
        with self.assertRaises(GuardError):api.publish(1,'Unsafe','a'*40)
    def test_other_users_marker_is_not_overwritten(self):
        api,calls=self.api([{'id':1,'body':MARKER,'user':{'type':'User','login':'owner'}}]);api.publish(1,'New','a'*40);self.assertEqual(calls[-1][0],'POST')

class ReadinessAndHistory(unittest.TestCase):
    def test_missing_credentials_report_all_prerequisites(self):
        self.assertEqual(len(prerequisites('','','',False)),4)
    def test_blocked_is_not_pass(self):
        self.assertIn('not a passing quality result',gate_summary(None,'Missing setup'))
    def test_immutable_sha_and_path_limits(self):
        for sha,path in [('HEAD','prompts/v1.yaml'),('a'*40,'../../secret')]:
            with self.assertRaises(GuardError):read_blob(ROOT,sha,path)
    def test_disabled_pair_cannot_make_provider_calls(self):
        calls=[]
        with self.assertRaises(GuardError):asyncio.run(evaluate_pair(ROOT,'a'*40,'b'*40,'prompts/v1.yaml','data/golden.json',Path('unused'),'','','',enabled=False,provider_factory=lambda:calls.append(1)))
        self.assertEqual(calls,[])
    def test_persisted_points_contain_no_email_or_output_text(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'points.json';run=make_run();series=record_point(p,run);text=p.read_text()
            point=json.loads(text)['points'][0]
            self.assertTrue({'email','raw','prediction','expected','summary'}.isdisjoint(point));self.assertNotIn('subscription',text)
            self.assertEqual(point_drift(series,run,Thresholds())['status'],'insufficient_history')
    def test_history_survives_new_process_loads(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'points.json';a=make_run();b=make_run('candidate','v2');record_point(p,a);series=record_point(p,b)
            self.assertEqual(len(series.points),2)

class EndToEndGate(unittest.TestCase):
    def gold_fixture(self):
        from modelguard.authoring import approve_case
        from modelguard.models import Dataset
        source=load_dataset(ROOT/'fixtures/dataset.json');cases=[]
        for i in range(64):
            c=source.cases[i%16].model_copy(deep=True);c.id=f'unit_{i}';c.email+=f' Unit-test distinct input {i}.'
            cases.append(approve_case(c,'SYNTHETIC UNIT TEST IDENTITY','approve'))
        return Dataset(schema_version=1,version='unit-contract-only',provenance='human_reviewed',
            description='Structurally simulated gold for a temporary unit test only; not actual human-reviewed data.',cases=cases)
    def test_edited_case_invalidates_review(self):
        from modelguard.dataset import validate_dataset
        data=self.gold_fixture();validate_dataset(data,require_gold=True);data.cases[0].email+=' Edited.'
        with self.assertRaisesRegex(GuardError,'content changed'):validate_dataset(data,require_gold=True)
    def test_pair_executes_both_runs_and_generates_evidence_without_network(self):
        import subprocess
        from modelguard.models import Observation
        data=self.gold_fixture();labels={c.id:c.expected for c in data.cases}
        class ContractProvider:
            mode='replay';model='unit-contract';fingerprint='unit-contract';judge_policy='unit-contract'
            async def classify(self,prompt,case):
                prediction=labels[case.id].model_copy()
                if prompt.version.endswith('candidate') and int(case.id.split('_')[1])<8:
                    prediction.category='account' if prediction.category!='account' else 'technical'
                return Observation(raw=prediction.model_dump_json())
            async def judge(self,*args):return Observation(raw='{"score":5,"reason":"Unit fixture score."}')
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td)/'repo';repo.mkdir();(repo/'prompts').mkdir();(repo/'data').mkdir()
            import shutil
            shutil.copyfile(ROOT/'prompts/v1.yaml',repo/'prompts/current.yaml');(repo/'data/golden.json').write_text(data.model_dump_json())
            def git(*args):return subprocess.check_output(['git',*args],cwd=repo).decode().strip()
            git('init','-q');git('config','user.name','Unit Test');git('config','user.email','unit@example.invalid');git('add','.');git('commit','-qm','unit base');base=git('rev-parse','HEAD')
            shutil.copyfile(ROOT/'prompts/v2.yaml',repo/'prompts/current.yaml');git('add','.');git('commit','-qm','unit candidate');head=git('rev-parse','HEAD')
            output=Path(td)/'results'
            result=asyncio.run(evaluate_pair(repo,base,head,'prompts/current.yaml','data/golden.json',output,'test-model','test-judge','not-real',enabled=True,provider_factory=ContractProvider))
            self.assertEqual(result['status'],'critical');self.assertEqual(len(result['regressions']),8)
            self.assertFalse(result['release_evidence']);self.assertTrue((output/'report.html').exists());self.assertTrue((output/'history-points.json').exists())
            # A new versioned file must compare to the configured baseline, not an unchanged file.
            shutil.copyfile(ROOT/'prompts/v1.yaml',repo/'prompts/current.yaml')
            shutil.copyfile(ROOT/'prompts/v2.yaml',repo/'prompts/new.yaml');git('add','.');git('commit','-qm','unit new prompt version')
            versionhead=git('rev-parse','HEAD')
            version_result=asyncio.run(evaluate_pair(repo,base,versionhead,'prompts/current.yaml','data/golden.json',output,'test-model','test-judge','not-real',enabled=True,provider_factory=ContractProvider))
            self.assertEqual(version_result['source']['candidate_prompt'],'prompts/new.yaml')
            self.assertEqual(version_result['source']['baseline_prompt'],'prompts/current.yaml')
            self.assertEqual(version_result['status'],'critical')
            (repo/'data/golden.json').write_text(data.model_dump_json()+'\n');git('add','.');git('commit','-qm','unit gold changed');newhead=git('rev-parse','HEAD')
            with self.assertRaisesRegex(GuardError,'Golden dataset changed'):
                asyncio.run(evaluate_pair(repo,base,newhead,'prompts/current.yaml','data/golden.json',output,'test-model','test-judge','not-real',enabled=True,provider_factory=ContractProvider))
