"""Tool argument JSON parser with auto-repair logic."""

import json
import re
import logging

logger = logging.getLogger(__name__)


def parse_tool_arguments_with_repair(name: str, tool_id: str, args_str: str, log) -> dict:
    if not args_str:
        return {}

    # First attempt: direct parse
    try:
        return json.loads(args_str)
    except json.JSONDecodeError as e:
        log.warning(
            "tool_call_json_parse_error_attempting_repair",
            tool_name=name,
            tool_id=tool_id,
            args_str_preview=args_str[:200],
            args_str_length=len(args_str),
            error_msg=str(e),
        )

    # Attempt auto-repair
    fixed_str = args_str
    repairs_applied = []

    # Fix 1: complete missing braces
    if not fixed_str.strip().endswith('}'):
        fixed_str = fixed_str.rstrip() + '}'
        repairs_applied.append("add_closing_brace")
    if not fixed_str.strip().startswith('{'):
        fixed_str = '{' + fixed_str.lstrip()
        repairs_applied.append("add_opening_brace")

    # Fix 2: escape unescaped control characters
    fixed_str = fixed_str.replace('\\n', '\x00NEWLINE\x00')
    fixed_str = fixed_str.replace('\\r', '\x00RETURN\x00')
    fixed_str = fixed_str.replace('\\t', '\x00TAB\x00')
    fixed_str = fixed_str.replace('\\\\', '\x00BACKSLASH\x00')

    if '\n' in fixed_str:
        fixed_str = fixed_str.replace('\n', '\\n')
        repairs_applied.append("escape_newlines")
    if '\r' in fixed_str:
        fixed_str = fixed_str.replace('\r', '\\r')
        repairs_applied.append("escape_returns")
    if '\t' in fixed_str:
        fixed_str = fixed_str.replace('\t', '\\t')
        repairs_applied.append("escape_tabs")

    fixed_str = fixed_str.replace('\x00NEWLINE\x00', '\\n')
    fixed_str = fixed_str.replace('\x00RETURN\x00', '\\r')
    fixed_str = fixed_str.replace('\x00TAB\x00', '\\t')
    fixed_str = fixed_str.replace('\x00BACKSLASH\x00', '\\\\')

    # Fix 3: remove trailing commas
    fixed_str = re.sub(r',\s*}', '}', fixed_str)
    fixed_str = re.sub(r',\s*]', ']', fixed_str)

    # Fix 4: complete missing string quotes
    quote_count = fixed_str.count('"') - fixed_str.count('\\"')
    if quote_count % 2 != 0 and fixed_str.rstrip().endswith('}'):
        fixed_str = fixed_str.rstrip()[:-1] + '"}'
        repairs_applied.append("add_closing_quote")

    # Second attempt
    try:
        args = json.loads(fixed_str)
        log.info(
            "tool_call_json_repaired_successfully",
            tool_name=name,
            tool_id=tool_id,
            repairs_applied=repairs_applied,
        )
        return args
    except json.JSONDecodeError:
        log.error(
            "tool_call_json_parse_error_repair_failed",
            tool_name=name,
            tool_id=tool_id,
            args_str_preview=args_str[:200],
            repairs_attempted=repairs_applied,
        )
        return {}
