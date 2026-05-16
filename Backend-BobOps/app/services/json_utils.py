"""
json_utils.py — JSON repair utility for LLM responses
"""

import json
import logging
import re

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Error raised when AI service returns invalid response."""


def repair_json(raw: str | None) -> dict:
    """Attempt to parse and repair JSON from AI responses.

    Cascading strategy — tries json.loads() after EACH step:
    1. Direct parse
    2. Strip markdown fences, extract first {...}
    3. State-machine escape of inner quotes in string values
    4. Regex repairs one by one (comments, trailing commas, unquoted keys,
       single quotes, missing commas, control chars, truncation)
    5. json5.loads() if available
    6. demjson3.decode() if available
    7. Final json.loads() with error context logging
    """
    if raw is None:
        raise AIServiceError("Respuesta vacía (None) de la AI")

    text = raw.strip()

    def _try() -> dict | None:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    # 1. Direct parse (fast path — ~80% of cases)
    result = _try()
    if result is not None:
        return result

    # 2. Strip markdown fences and extract first {...}
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        text = match.group(0)

    result = _try()
    if result is not None:
        return result

    # 2.5. Escape unescaped inner quotes in value strings (state machine)
    text = _escape_inner_quotes(text)

    result = _try()
    if result is not None:
        return result

    # 3. Apply each regex repair sequentially, checking after each
    repairs = [
        ("remove line comments //",       lambda t: re.sub(r'//.*', '', t)),
        ("remove block comments /* */",   lambda t: re.sub(r'/\*.*?\*/', '', t, flags=re.DOTALL)),
        ("remove trailing commas",        lambda t: re.sub(r',(\s*[}\]])', r'\1', t)),
        ("quote unquoted keys",           lambda t: re.sub(r'(?<!")(\b[a-zA-Z_]\w*\b)(?=\s*:)', r'"\1"', t)),
        ("convert single to double quotes", lambda t: re.sub(r"(?<!\\)'(.*?)(?<!\\)'", r'"\1"', t)),
        ("add missing commas before keys", lambda t: re.sub(r'(?<=[}\]"\d])\s+(?=")', ', ', t)),
        ("add missing commas after bool/null", lambda t: re.sub(r'\b(true|false|null)\s+(?=")', r'\1, ', t)),
        ("fix truncated JSON",             lambda t: _fix_truncated_json(t)),
        ("strip control characters",       lambda t: re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', t)),
    ]

    for step_name, fn in repairs:
        text = fn(text)
        result = _try()
        if result is not None:
            return result

    # 4. Try json5 if installed (lenient JSON parser)
    try:
        import json5 as json5_lib
        return json5_lib.loads(text)
    except ImportError:
        pass
    except Exception:
        pass

    # 5. Try demjson3 if installed (even more lenient parser)
    try:
        import demjson3 as demjson3_lib
        return demjson3_lib.decode(text)
    except ImportError:
        pass
    except Exception:
        pass

    # 6. Final attempt with context logging
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        ctx = _error_context(text, e.pos)
        logger.error("JSON inválido incluso tras reparación (col %d). Contexto: %s", e.pos, ctx)
        raise AIServiceError(f"JSON inválido tras reparación (columna {e.pos}): {ctx}")


def _fix_truncated_json(text: str) -> str:
    """Add missing closing brackets at the end of truncated JSON using a stack."""
    stack: list[str] = []
    in_string = False
    escape = False

    for ch in text:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in '{[':
            stack.append(ch)
        elif ch == '}':
            if stack and stack[-1] == '{':
                stack.pop()
        elif ch == ']':
            if stack and stack[-1] == '[':
                stack.pop()

    closing = ''.join('}' if opener == '{' else ']' for opener in reversed(stack))
    return text + closing


def _escape_inner_quotes(text: str) -> str:
    """Escape double quotes that appear inside JSON string values (unclosed).

    Uses a context stack to track key/value positions, so structural quotes
    (that close a key or value) are left alone while content quotes in
    Spanish text (e.g. "específicas") are escaped with backslash.
    """
    result = []
    in_string = False
    escape = False
    ctx_stack: list[str] = []

    i = 0
    while i < len(text):
        c = text[i]

        if escape:
            result.append(c)
            escape = False
            i += 1
            continue

        if c == '\\':
            result.append(c)
            escape = True
            i += 1
            continue

        if c == '"':
            if not in_string:
                in_string = True
                result.append(c)
            else:
                expect_key = ctx_stack[-1] == 'obj_key' if ctx_stack else False
                if expect_key:
                    in_string = False
                    result.append(c)
                else:
                    j = i + 1
                    while j < len(text) and text[j] in ' \t\n\r':
                        j += 1
                    next_c = text[j] if j < len(text) else ''
                    if next_c in ',]})' or next_c == '':
                        in_string = False
                        result.append(c)
                    else:
                        result.append('\\"')
            i += 1
            continue

        if not in_string:
            if c == '{':
                ctx_stack.append('obj_key')
            elif c == '[':
                ctx_stack.append('arr')
            elif c == '}':
                if ctx_stack:
                    ctx_stack.pop()
            elif c == ']':
                if ctx_stack:
                    ctx_stack.pop()
            elif c == ':':
                if ctx_stack and ctx_stack[-1] == 'obj_key':
                    ctx_stack[-1] = 'obj_val'
            elif c == ',':
                if ctx_stack and ctx_stack[-1] == 'obj_val':
                    ctx_stack[-1] = 'obj_key'

        result.append(c)
        i += 1

    return ''.join(result)


def _error_context(text: str, pos: int, window: int = 60) -> str:
    """Return a snippet around the error position for debugging."""
    start = max(0, pos - window)
    end = min(len(text), pos + window)
    snippet = text[start:end]
    return f"...{repr(snippet)}..."
