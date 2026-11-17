# docs_macros.py
import argparse
import importlib
import os
import sys
from contextlib import contextmanager

@contextmanager
def _patched(prog, columns):
    old_argv0 = sys.argv[0]
    old_env = {k: os.environ.get(k) for k in ("COLUMNS", "NO_COLOR")}
    if prog:
        sys.argv[0] = prog
    os.environ["COLUMNS"] = str(columns)
    os.environ["NO_COLOR"] = "1"   # keeps newer Pythons from adding colour codes
    try:
        yield
    finally:
        sys.argv[0] = old_argv0
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

def _walk(parser, level):
    out = [
        f"{'#' * level} `{parser.prog}`\n",
        "```text\n" + parser.format_help().rstrip() + "\n```\n",
    ]
    for action in parser._actions:  # pylint: disable=W0212
        if isinstance(action, argparse._SubParsersAction): # pylint: disable=W0212
            for sub in action.choices.values():
                out += _walk(sub, level + 1)
    return out

def define_env(env):
    @env.macro
    def cli_help(module, func="build_parser", prog=None, level=2, columns=80):
        with _patched(prog, columns):
            parser = getattr(importlib.import_module(module), func)()
            return "\n".join(_walk(parser, level))
