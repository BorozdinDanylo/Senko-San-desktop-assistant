import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from core.components import types
except ModuleNotFoundError:
    types = None


@unittest.skipIf(types is None, 'history dependencies are unavailable')
class HistoryRedactionStorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_messages_are_masked_and_old_rows_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / 'history.db'
            prompt = root / 'prompt'
            prompt.write_text('instructions', encoding='utf-8')
            old = json.dumps({'role': 'user', 'content': 'password=old-example'})
            with sqlite3.connect(database) as db:
                db.execute('CREATE TABLE messages (id INTEGER PRIMARY KEY, chunk_id INTEGER NOT NULL, position INTEGER NOT NULL UNIQUE, data TEXT NOT NULL)')
                db.execute('INSERT INTO messages (chunk_id, position, data) VALUES (0, 0, ?)', (old,))
            with patch.object(types, 'HISTORY_DB_PATH', database), patch.object(types, 'SYSTEM_SENKO_PROMPT', prompt), patch.object(types, 'MAIN_MEMORIES_PATH', root / 'missing'), patch.object(types, 'NOTES_TO_NEXT_START_PATH', root / 'missing'):
                history = types.History.__new__(types.History)
                await history.load()
                try:
                    await history.add({'type': 'function_call_output', 'output': 'password=new-example'})
                    await history._save_history()
                    with sqlite3.connect(database) as db:
                        rows = [json.loads(row[0]) for row in db.execute('SELECT data FROM messages ORDER BY position')]
                    self.assertEqual(rows[0]['content'], 'password=old-example')
                    self.assertEqual(rows[1]['output'], 'password=[REDACTED]')
                finally:
                    await history._db.close()
