"""CI checks expected system behavior, not the quality of a real model."""
import json
from pathlib import Path
import sys
r=json.loads(Path(sys.argv[1]).read_text())
assert r['gate']=='critical',r
assert r['regressions']==4 and r['improvements']==1,r
assert r['recovery_gate']=='pass',r
assert r['slow_drift_fixture']=='warning',r
assert r['slack_delivery'].startswith('not sent'),r
print('Regression, recovery, slow-drift and offline-delivery contracts passed.')
