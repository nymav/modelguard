"""Prepare alerts offline. Network delivery is a separate explicit operation."""
import json
import re
import urllib.request
from urllib.parse import urlsplit
from .config import GuardError
from .providers import NoRedirect

def slack_payload(comparison: dict, baseline, candidate, report_url: str | None=None) -> dict:
    text=(f"ModelGuard {comparison['status']}: {len(comparison['regressions'])} regressions; "
          f"pass rate {100*baseline.summary['pass_rate']:.1f}% → {100*candidate.summary['pass_rate']:.1f}%. "
          f"Source: {candidate.provenance}/{candidate.provider}.")
    blocks=[{'type':'section','text':{'type':'plain_text','text':text}}]
    if report_url:
        url=urlsplit(report_url)
        if url.scheme!='https' or not url.hostname or url.username or url.password:
            raise GuardError('Report link must be an HTTPS URL without credentials')
        blocks.append({'type':'section','text':{'type':'plain_text','text':'Report: '+report_url}})
    return {'text':text,'blocks':blocks}

def send_slack(webhook: str, payload: dict, *, opener=None):
    parsed=urlsplit(webhook)
    if parsed.scheme!='https' or parsed.hostname!='hooks.slack.com' or not re.fullmatch(r'/services/[A-Za-z0-9_/-]+', parsed.path) or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.port not in (None,443):
        raise GuardError('Expected an official Slack incoming webhook URL')
    data=json.dumps(payload).encode()
    if len(data)>100000: raise GuardError('Slack payload exceeds size limit')
    req=urllib.request.Request(webhook,data,{'Content-Type':'application/json'},method='POST')
    try:
        with (opener or urllib.request.build_opener(NoRedirect())).open(req,timeout=15) as response:
            if response.status!=200 or response.read(100)!=b'ok': raise GuardError('Slack did not confirm delivery')
    except GuardError: raise
    except Exception: raise GuardError('Slack delivery failed; webhook URL withheld') from None
