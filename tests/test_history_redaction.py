import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "history_redaction", Path(__file__).resolve().parents[1] / "core/src/core/components/history_redaction.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
REDACTED, redact_history = module.REDACTED, module.redact_history


class HistoryRedactionTests(unittest.TestCase):
    def test_explicit_credentials(self):
        examples = [
            ('Authorization: Bearer ' + 'a' * 24, 'Authorization: Bearer ' + REDACTED),
            ('sk-proj-' + 'x' * 24, REDACTED),
            ('ghp_' + 'x' * 30, REDACTED),
            ('AKIA' + 'A' * 16, REDACTED),
            ('password="example password"', 'password="' + REDACTED + '"'),
            ("api_key: 'example-key'", "api_key: '" + REDACTED + "'"),
            ('access_token=example-token', 'access_token=' + REDACTED),
        ]
        for original, expected in examples:
            with self.subTest(expected=expected):
                self.assertEqual(redact_history(original), expected)

    def test_json_arguments_remain_valid(self):
        arguments = json.dumps({"password": 'example"value', "query": "hello"})
        self.assertEqual(json.loads(redact_history(arguments)), {"password": REDACTED, "query": "hello"})
        self.assertEqual(json.loads(redact_history('{"password": null, "api_key": 123}')), {"password": None, "api_key": 123})

    def test_nested_tool_output_and_regular_text(self):
        original = {'type': 'function_call_output', 'output': ['password=hunter2', 'The password field is required.', 42]}
        result = redact_history(original)
        self.assertEqual(result['output'], ['password=' + REDACTED, 'The password field is required.', 42])
        self.assertEqual(original['output'][0], 'password=hunter2')
        self.assertEqual(redact_history({'password': 'example'}), {'password': REDACTED})
        self.assertEqual(redact_history('A key to success and token counts: 123.'), 'A key to success and token counts: 123.')

    def test_nested_json_keeps_structure_and_redacts_inner_strings(self):
        original = json.dumps({'password': {'hint': 'ordinary text'}, 'items': [
            json.dumps({'secret_key': 'example', 'count': 2}), {'access_token': 'example'}]})
        result = json.loads(redact_history(original))
        self.assertEqual(result['password'], {'hint': 'ordinary text'})
        self.assertEqual(json.loads(result['items'][0]), {'secret_key': REDACTED, 'count': 2})
        self.assertEqual(result['items'][1], {'access_token': REDACTED})
        unchanged = '{ "password": {"hint": "ordinary text"}, "values": [1, null] }'
        self.assertEqual(redact_history(unchanged), unchanged)
