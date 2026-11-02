"""Same-repository PR summary publishing with stale-head and bot-owner guards."""
import json
import re
import urllib.request
from .config import GuardError
from .providers import NoRedirect

MARKER='<!-- modelguard:release-gate:v1 -->'
class GitHubSummary:
    def __init__(self, repository: str, token: str, *, transport=None):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):raise GuardError('Invalid GitHub repository')
        if not token or '\n' in token or '\r' in token:raise GuardError('GitHub token is required')
        self.repository=repository;self.token=token;self.transport=transport or self._http
    def _http(self,method,path,payload=None):
        request=urllib.request.Request('https://api.github.com'+path,
            json.dumps(payload).encode() if payload is not None else None,
            {'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'ModelGuard'},method=method)
        try:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=20) as response:
                raw=response.read(2_000_001)
                if len(raw)>2_000_000:raise GuardError('GitHub response exceeds limit')
                return json.loads(raw)
        except Exception:raise GuardError('GitHub summary API operation failed; credentials withheld') from None
    def publish(self,pr:int,body:str,expected_head:str):
        if type(pr)is not int or pr<=0 or not re.fullmatch(r'[a-f0-9]{40,64}',expected_head):raise GuardError('Invalid PR number or expected commit')
        if len(body)>30000:raise GuardError('PR summary too large')
        prefix='/repos/'+self.repository
        def verify():
            value=self.transport('GET',prefix+f'/pulls/{pr}')
            if value.get('state')!='open' or value.get('head',{}).get('repo',{}).get('full_name')!=self.repository:raise GuardError('Publishing requires an open same-repository PR')
            if value.get('head',{}).get('sha')!=expected_head:raise GuardError('PR head changed; refuse stale summary')
        verify();existing=None
        for page in range(1,11):
            comments=self.transport('GET',prefix+f'/issues/{pr}/comments?per_page=100&page={page}')
            if not isinstance(comments,list):raise GuardError('Invalid GitHub comments response')
            for comment in comments:
                user=comment.get('user',{})
                if user.get('type')=='Bot' and user.get('login')=='github-actions[bot]' and isinstance(comment.get('body'),str) and MARKER in comment['body']:
                    existing=comment;break
            if existing or len(comments)<100:break
        else:raise GuardError('Comment pagination budget exceeded')
        verify();payload={'body':MARKER+'\n'+body}
        if existing:
            identifier=existing.get('id')
            if type(identifier)is not int:raise GuardError('Invalid existing comment ID')
            result=self.transport('PATCH',prefix+f'/issues/comments/{identifier}',payload)
        else:result=self.transport('POST',prefix+f'/issues/{pr}/comments',payload)
        return {'comment_id':result.get('id'),'updated':existing is not None}
