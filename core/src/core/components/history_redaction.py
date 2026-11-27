"""Conservative redaction for newly persisted conversation history."""

import json
import re

REDACTED = "[REDACTED]"

# Only explicit credential labels and recognizable token prefixes are handled.
_PATTERNS = (
    re.compile(r'(?i)(\bBearer\s+)([A-Za-z0-9._~+/=-]{8,})'),
    re.compile(r'\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b'),
    re.compile(
        r'''(?ix)(["']?\b(?:password|passwd|api[_-]?key|access[_-]?token|secret[_-]?key)\b["']?\s*[:=]\s*)'''
        r'''(?:"(?:\\.|[^"\\\r\n])+"|'(?:\\.|[^'\\\r\n])+'|[^\s,;}&]+)'''
    ),
)


def redact_history(value):
    """Return a copy with recognizable secrets masked, without changing keys."""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (ValueError, RecursionError):
            parsed = None
        if isinstance(parsed, (dict, list)):
            redacted = redact_history(parsed)
            return value if redacted == parsed else json.dumps(redacted, ensure_ascii=False)
        value = _PATTERNS[0].sub(lambda match: match.group(1) + REDACTED, value)
        value = _PATTERNS[1].sub(REDACTED, value)
        def replace_assignment(match):
            matched = match.group(0)[len(match.group(1)):]
            if matched in ("null", "true", "false") or re.fullmatch(r"-?\d+(?:\.\d+)?", matched):
                return match.group(0)
            quote = matched[0] if matched[0] in ('\"', "'") else ''
            return match.group(1) + quote + REDACTED + quote

        return _PATTERNS[2].sub(replace_assignment, value)
    if isinstance(value, list):
        return [redact_history(item) for item in value]
    if isinstance(value, dict):
        return {
            key: REDACTED if isinstance(key, str) and isinstance(item, str)
            and re.fullmatch(r"(?i)(?:password|passwd|api[_-]?key|access[_-]?token|secret[_-]?key)", key)
            and item else redact_history(item)
            for key, item in value.items()
        }
    return value
