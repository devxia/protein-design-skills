"""Malformed tool-output payloads must never crash hooks with a traceback (#27)."""

from __future__ import annotations

import io
import json

import pytest

from tests.helpers import load_hook_module

HOOKS = [
    load_hook_module("design-complete-notify"),
    load_hook_module("pipeline-orchestrator"),
    load_hook_module("format-converter"),
    load_hook_module("quality-gate"),
]

MALFORMED_PAYLOADS = [
    {"result": {"content": ["not-a-dict"]}},
    {"result": {"content": [None]}},
    {"result": {"content": [{"text": 123}]}},
    {"result": {"content": "a-string"}},
    {"result": {"content": []}},
    {"result": "not-a-dict"},
]


@pytest.mark.parametrize("payload", MALFORMED_PAYLOADS)
def test_hooks_survive_malformed_payloads(monkeypatch, capsys, payload):
    for module in HOOKS:
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        rc = module.main()
        captured = capsys.readouterr()
        assert rc == 0, f"{module.__name__} returned {rc}"
        assert "Traceback" not in captured.err, f"{module.__name__} crashed: {captured.err}"
