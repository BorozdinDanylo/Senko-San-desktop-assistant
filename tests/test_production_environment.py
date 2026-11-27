import importlib.util
from importlib.machinery import ModuleSpec
from pathlib import Path
import tempfile
from types import ModuleType
import unittest


SOURCE: Path = Path(__file__).resolve().parents[1] / 'deployment/migrate_environment.py'
SPEC: ModuleSpec | None = importlib.util.spec_from_file_location('migrate_environment', SOURCE)
assert SPEC is not None and SPEC.loader is not None
MIGRATION: ModuleType = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


class ProductionEnvironmentTests(unittest.TestCase):
    def test_migration_quotes_values_and_protects_both_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root: Path = Path(directory)
            source: Path = root / '.env'
            destination: Path = root / 'etc/core.env'
            archive: Path = root / 'etc/legacy.env'
            source.write_text('OPENAI_API_KEY=example\nSENKO_SAN_API_KEY=example\nSENKO_SAN_VOICE_ID=voice\nEXTRA=\'a"b$c`d\\e\'\n')
            MIGRATION.migrate_environment(source, destination, archive)
            self.assertFalse(source.exists())
            self.assertIn('EXTRA="a\\"b\\$c\\`d\\\\e"', destination.read_text())
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            self.assertEqual(archive.stat().st_mode & 0o777, 0o600)
            self.assertEqual(destination.parent.stat().st_mode & 0o777, 0o700)

    def test_existing_environment_is_preserved_and_migration_is_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root: Path = Path(directory)
            source: Path = root / '.env'
            destination: Path = root / 'core.env'
            archive: Path = root / 'legacy.env'
            content: str = 'OPENAI_API_KEY=existing\nSENKO_SAN_API_KEY=existing\nSENKO_SAN_VOICE_ID=existing\n'
            destination.write_text(content)
            source.write_text('old checkout credentials')
            MIGRATION.migrate_environment(source, destination, archive)
            MIGRATION.migrate_environment(source, destination, archive)
            self.assertEqual(destination.read_text(), content)
            self.assertEqual(archive.read_text(), 'old checkout credentials')

    def test_missing_credentials_and_symlinks_do_not_move_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root: Path = Path(directory)
            source: Path = root / '.env'
            source.write_text('INCOMPLETE=example\n')
            destination: Path = root / 'core.env'
            archive: Path = root / 'legacy.env'
            with self.assertRaises(ValueError):
                MIGRATION.migrate_environment(source, destination, archive)
            self.assertTrue(source.exists())
            self.assertFalse(destination.exists())
            destination.symlink_to(source)
            with self.assertRaises(ValueError):
                MIGRATION.migrate_environment(source, destination, archive)
            self.assertEqual(source.read_text(), 'INCOMPLETE=example\n')
