"""Immutable SQLite run history and explicit, checked baseline selection."""
from pathlib import Path
import sqlite3
from .models import Run
from .comparison import validate_run
from .config import GuardError

class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection=sqlite3.connect(path, timeout=10)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA busy_timeout=10000')
        self.connection.executescript('''
        CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, dataset_hash TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS run_dataset ON runs(dataset_hash, created_at);
        CREATE TABLE IF NOT EXISTS baselines (name TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id));
        ''')
        self.connection.execute('PRAGMA foreign_keys=ON')
    def close(self): self.connection.close()
    def add(self, run: Run):
        validate_run(run)
        try:
            with self.connection: self.connection.execute('INSERT INTO runs VALUES (?,?,?,?)', (run.id,run.created_at,run.dataset_hash,run.model_dump_json()))
        except sqlite3.IntegrityError: raise GuardError('Run ID already exists; runs are immutable') from None
    def get(self, run_id: str) -> Run:
        row=self.connection.execute('SELECT payload FROM runs WHERE id=?',(run_id,)).fetchone()
        if not row: raise GuardError('Run not found')
        return validate_run(Run.model_validate_json(row[0]))
    def history(self, dataset_hash: str, limit: int=100) -> list[Run]:
        if not 1<=limit<=1000: raise GuardError('Invalid history limit')
        rows=self.connection.execute('SELECT payload FROM runs WHERE dataset_hash=? ORDER BY created_at DESC,id DESC LIMIT ?', (dataset_hash,limit)).fetchall()
        return [validate_run(Run.model_validate_json(row[0])) for row in reversed(rows)]
    def promote(self, name: str, run_id: str, *, allow_fixture: bool=False):
        run=self.get(run_id)
        if run.summary['errors']: raise GuardError('Cannot approve a baseline with errors')
        if not allow_fixture and (run.provenance!='human_reviewed' or run.provider!='openai'):
            raise GuardError('Production baseline requires a live, human-reviewed dataset run')
        with self.connection:
            self.connection.execute('INSERT INTO baselines VALUES (?,?) ON CONFLICT(name) DO UPDATE SET run_id=excluded.run_id',(name,run_id))
    def baseline(self, name: str) -> Run:
        row=self.connection.execute('SELECT run_id FROM baselines WHERE name=?',(name,)).fetchone()
        if not row: raise GuardError('Named baseline not configured')
        return self.get(row[0])
