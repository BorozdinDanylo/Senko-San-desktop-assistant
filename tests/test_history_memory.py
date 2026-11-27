import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.components import types


class HistoryMemoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.prompt = root / 'prompt.md'
        self.main = root / 'main.md'
        self.notes = root / 'notes.md'
        self.database = root / 'history.db'
        self.prompt.write_text('instructions', encoding='utf-8')
        for name, value in (('SYSTEM_SENKO_PROMPT', self.prompt),
                            ('MAIN_MEMORIES_PATH', self.main),
                            ('NOTES_TO_NEXT_START_PATH', self.notes),
                            ('HISTORY_DB_PATH', self.database)):
            patcher = patch.object(types, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_optional_files_are_independent_and_missing_is_safe(self):
        self.notes.write_text('next start', encoding='utf-8')
        chunk = types.History.create_first_chunk(is_program_starting=True)
        self.assertEqual([item['content'] for item in chunk], ['instructions', 'next start'])
        self.main.write_text('main', encoding='utf-8')
        self.notes.unlink()
        chunk = types.History.create_first_chunk(is_program_starting=True)
        self.assertEqual([item['content'] for item in chunk], ['instructions', 'main'])
        self.main.unlink()
        self.assertEqual(len(types.History.create_first_chunk(True)), 1)

    def test_corrupt_memory_is_reported(self):
        self.main.write_bytes(b'\xff')
        with self.assertRaises(UnicodeDecodeError):
            types.History.create_first_chunk(True)

    async def test_load_keeps_startup_notes_once_and_persists_history(self):
        self.main.write_text('main', encoding='utf-8')
        self.notes.write_text('next start', encoding='utf-8')
        history = types.History.__new__(types.History)
        await history.load()
        self.addAsyncCleanup(history._db.close)
        await history.add({'role': 'user', 'content': 'hello'})
        other = types.History.__new__(types.History)
        await other.load()
        self.addAsyncCleanup(other._db.close)
        self.assertEqual([item['content'] for item in other.get()],
                         ['instructions', 'main', 'next start', 'hello'])
        self.assertEqual([item['content'] for item in types.History.create_first_chunk()],
                         ['instructions', 'main'])

    async def test_corrupt_database_is_not_replaced(self):
        self.database.write_bytes(b'not a database')
        history = types.History.__new__(types.History)
        with self.assertRaises(Exception):
            await history.load()
        if history._db is not None:
            await history._db.close()
        self.assertEqual(self.database.read_bytes(), b'not a database')
