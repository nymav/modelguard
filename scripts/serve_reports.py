"""Loopback-only read-only preview of generated artifacts; not a hosted service."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8793);p.add_argument('--directory',type=Path,default=Path('artifacts/demo'))
a=p.parse_args();root=a.directory.resolve()
if not root.is_dir():p.error('Generate the demo first')
handler=partial(SimpleHTTPRequestHandler,directory=str(root))
print(f'Local report: http://127.0.0.1:{a.port}/regression/report.html',flush=True)
ThreadingHTTPServer(('127.0.0.1',a.port),handler).serve_forever()
