import hashlib
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

def canonical(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/'), '', ''))

class Ledger:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS applications(url TEXT PRIMARY KEY,status TEXT,day TEXT,detail TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS controls(name TEXT PRIMARY KEY,value TEXT)')
    def connect(self):
        return sqlite3.connect(self.path, timeout=30)
    def status(self, url):
        with self.connect() as db:
            row = db.execute('SELECT status FROM applications WHERE url=?', (canonical(url),)).fetchone()
            return row[0] if row else None
    def claim(self, url, limit):
        day = datetime.now(timezone.utc).date().isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT 1 FROM controls WHERE name='paused' AND value='true'").fetchone():
                return False
            if db.execute('SELECT COUNT(*) FROM applications WHERE day=? AND status IN (?,?,?)', (day,'submitted','submitting','uncertain')).fetchone()[0] >= limit:
                return False
            old = db.execute('SELECT status FROM applications WHERE url=?', (canonical(url),)).fetchone()
            if old and old[0] != 'retry':
                return False
            db.execute('INSERT OR REPLACE INTO applications VALUES(?,?,?,?)', (canonical(url),'submitting',day,''))
            return True
    def finish(self, url, status, detail):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO applications VALUES(?,?,?,?)', (canonical(url),status,datetime.now(timezone.utc).date().isoformat(),detail))
    def summary(self):
        with self.connect() as db:
            return {'counts':dict(db.execute('SELECT status,COUNT(*) FROM applications GROUP BY status')),
                    'recent':db.execute('SELECT url,status,detail FROM applications ORDER BY rowid DESC LIMIT 10').fetchall()}
    def pause(self, value):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO controls VALUES('paused',?)", ('true' if value else 'false',))
    def is_paused(self):
        with self.connect() as db:
            return bool(db.execute("SELECT 1 FROM controls WHERE name='paused' AND value='true'").fetchone())
