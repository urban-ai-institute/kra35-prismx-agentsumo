"""
Tests that the prompts only name tools the agent can actually call:
1. Every tool name in the system prompt, the context/web instructions and
   the additional-file guides exists on the SUMO, SQLite or Filesystem MCP
2. Worked examples run xml_to_sqlite_tool before querying a simulation
"""

import ast
import importlib.util
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).parent.parent
AGENT_DIR = PROJECT_ROOT / "agentsumo" / "agent"

SQLITE_TOOLS = {"read_query", "write_query", "create_table", "list_tables", "describe_table", "append_insight"}

# Tools listed by the npm @modelcontextprotocol/server-filesystem server
FILESYSTEM_TOOLS = {
    "read_text_file", "read_file", "read_media_file", "read_multiple_files",
    "write_file", "edit_file", "create_directory", "list_directory",
    "list_directory_with_sizes", "directory_tree", "move_file", "search_files",
    "get_file_info", "list_allowed_directories",
}

SNAKE = r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+"


def _sumo_tools():
    """Names of the @mcp.tool() functions in the SUMO MCP server the agent launches."""
    spec = importlib.util.find_spec("agentsumo_mcp")  # locates without importing
    main_py = Path(spec.origin).parent / "main.py"
    tree = ast.parse(main_py.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                func = deco.func if isinstance(deco, ast.Call) else deco
                if isinstance(func, ast.Attribute) and func.attr == "tool":
                    names.add(node.name)
    assert len(names) > 20, f"could not read the SUMO tool list from {main_py}"
    return names


def _prompt_texts():
    files = sorted((AGENT_DIR / "prompts" / "templates").glob("*.md"))
    files += sorted((AGENT_DIR / "additional_files_guide").glob("*.md"))
    files.append(AGENT_DIR / "prompts" / "prompt_builder.py")
    return {f.relative_to(PROJECT_ROOT).as_posix(): f.read_text(encoding="utf-8") for f in files}


def _fenced_steps(text):
    """Snake-case names that start numbered steps inside ``` blocks."""
    steps, fenced = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        match = re.match(rf"\s*\d+\.\s+({SNAKE})\b", line)
        if fenced and match:
            steps.append(match.group(1))
    return steps


def _tool_mentions(text, real):
    mentions = set(re.findall(rf"\b{SNAKE}_tool\b", text))
    mentions |= set(re.findall(r"\btls_[a-z0-9_]+\b", text))
    # A real tool's name without its _tool suffix, e.g. "reduce_lanes"
    short_names = {name[: -len("_tool")] for name in real if name.endswith("_tool")}
    mentions |= {tok for tok in re.findall(rf"\b{SNAKE}\b", text) if tok in short_names}
    # Members of workflow chains: a → b → c
    for line in text.splitlines():
        if "→" in line:
            for part in line.split("→"):
                part = part.strip(" `*:-")
                if re.fullmatch(SNAKE, part):
                    mentions.add(part)
    # SQLite / Filesystem style names in backticks
    verbs = "read|write|edit|list|create|describe|append|move|search|get|directory"
    for span in re.findall(r"`([^`\n]+)`", text):
        if re.fullmatch(rf"(?:{verbs})_[a-z0-9_]+", span):
            mentions.add(span)
    mentions |= set(_fenced_steps(text))
    return mentions


def test_prompts_name_only_real_tools():
    real = _sumo_tools() | SQLITE_TOOLS | FILESYSTEM_TOOLS

    unknown = {
        path: sorted(_tool_mentions(text, real) - real)
        for path, text in _prompt_texts().items()
    }

    assert not any(unknown.values()), {path: names for path, names in unknown.items() if names}


def test_examples_store_results_before_querying():
    for path, text in _prompt_texts().items():
        pending = False  # a sumo_runner whose results are not in SQLite yet
        for step in _fenced_steps(text):
            if step == "sumo_runner":
                pending = True
            elif step == "xml_to_sqlite_tool":
                pending = False
            elif step == "read_query":
                assert not pending, f"{path}: read_query right after sumo_runner, without xml_to_sqlite_tool"
