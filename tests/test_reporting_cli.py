import asyncio
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from modelguard.config import Thresholds, GuardError
from modelguard.comparison import compare
from modelguard.reporting import render_html, write_report
from modelguard.notifications import slack_payload, send_slack
from modelguard.cli import main
from modelguard.store import Store
from helpers import make_run, ROOT

class Reporting(unittest.TestCase):
    def setUp(self):self.b=make_run();self.c=make_run('candidate','v2');self.diff=compare(self.b,self.c,Thresholds())
    def test_untrusted_output_is_escaped(self):
        self.c.cases[0].prediction.summary='<script>alert(1)</script>'
        html=render_html(self.b,self.c,self.diff,[self.b,self.c],{'status':'insufficient_history'})
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
    def test_report_explains_fixture_provenance_and_statistical_limits(self):
        html=render_html(self.b,self.c,self.diff,[],{'status':'insufficient_history'})
        self.assertIn('not measured live-model quality',html);self.assertIn('not statistical significance',html)
    def test_absent_telemetry_is_not_zero(self):
        html=render_html(self.b,self.c,self.diff,[],{'status':'insufficient_history'});self.assertIn('Not measured',html)
    def test_artifacts_have_same_comparison(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td);write_report(path,self.b,self.c,self.diff,[],{'status':'insufficient_history'})
            self.assertEqual(json.loads((path/'comparison.json').read_text())['comparison'],self.diff)
            self.assertTrue((path/'report.html').is_file())
    def test_slack_payload_does_not_include_email_text(self):
        payload=json.dumps(slack_payload(self.diff,self.b,self.c));self.assertNotIn('subscription',payload);self.assertIn('synthetic_fixture',payload)
    def test_slack_only_official_endpoint(self):
        with self.assertRaises(GuardError):send_slack('https://attacker.example/webhook',{})
    def test_report_url_cannot_leak_credentials(self):
        with self.assertRaises(GuardError):slack_payload(self.diff,self.b,self.c,'https://user:password@example.com')

class CLI(unittest.TestCase):
    def invoke(self,args):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code=main(args)
        return code,output.getvalue()
    def test_validate_fixture_explicit_provenance(self):
        code,out=self.invoke(['validate-dataset',str(ROOT/'fixtures/dataset.json')]);self.assertEqual(code,0);self.assertIn('synthetic_fixture',out)
    def test_release_dataset_gate_fails_fixture(self):
        code,out=self.invoke(['validate-dataset',str(ROOT/'fixtures/dataset.json'),'--require-gold']);self.assertEqual(code,3)
    def test_compare_returns_critical_exit_code(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'history.sqlite';s=Store(db);b=make_run();c=make_run('candidate','v2');s.add(b);s.add(c);s.close()
            code,out=self.invoke(['compare','--db',str(db),'--baseline',b.id,'--candidate',c.id,'--output',str(Path(td)/'report')])
            self.assertEqual(code,2);self.assertIn('critical',out)
    def test_missing_baseline_is_error_not_pass(self):
        with tempfile.TemporaryDirectory() as td:
            code,out=self.invoke(['compare','--db',str(Path(td)/'history.sqlite'),'--baseline','missing','--candidate','missing','--output',td]);self.assertEqual(code,3)
    def test_notifications_are_dry_run_without_explicit_flag(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'payload.json';path.write_text('{"text":"test"}')
            code,out=self.invoke(['notify','--payload',str(path)]);self.assertEqual(code,0);self.assertIn('dry_run',out)

    def test_demo_can_be_repeated_in_same_output_directory(self):
        with tempfile.TemporaryDirectory() as td:
            first,_=self.invoke(['demo','--output',td])
            second,_=self.invoke(['demo','--output',td])
            self.assertEqual(first,0);self.assertEqual(second,0)
            result=json.loads((Path(td)/'demo.json').read_text())
            self.assertEqual(result['gate'],'critical');self.assertEqual(result['recovery_gate'],'pass')
