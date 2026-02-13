"""
Unit tests for the @log_function decorator (service/logging_utils.py).

Tests parameter logging, return value summarization, sensitive value masking,
and timing behavior — all without any external dependencies.

Uses unittest.mock to mock the module logger so we can check what
logger.info() was called with. No caplog propagation issues.
"""

import logging
import time
from unittest.mock import patch, MagicMock

import pytest

from service.logging_utils import log_function, _summarize, _format_params
import service.logging_utils as logging_utils_module


# ── _summarize tests ─────────────────────────────────────────────────

class TestSummarize:
    def test_none(self):
        assert _summarize(None) == "None"

    def test_short_string(self):
        assert _summarize("hello") == "str: hello"

    def test_long_string_truncated(self):
        long = "x" * 200
        result = _summarize(long)
        assert result.startswith("str(200 chars)")
        assert "..." in result

    def test_list(self):
        assert _summarize([1, 2, 3]) == "list(3 items)"

    def test_empty_list(self):
        assert _summarize([]) == "list(0 items)"

    def test_tuple(self):
        assert _summarize((1, 2)) == "tuple(2 items)"

    def test_dict(self):
        result = _summarize({"a": 1, "b": 2})
        assert "dict(2 keys" in result

    def test_int(self):
        assert _summarize(42) == "42"

    def test_float(self):
        assert _summarize(3.14) == "3.14"

    def test_bool(self):
        assert _summarize(True) == "True"
        assert _summarize(False) == "False"


# ── _format_params tests ─────────────────────────────────────────────

class TestFormatParams:
    def test_simple_params(self):
        def func(x, y):
            pass
        result = _format_params(func, (1, 2), {})
        assert "x=1" in result
        assert "y=2" in result

    def test_sensitive_masking(self):
        def func(api_key, name):
            pass
        result = _format_params(func, ("secret123", "test"), {})
        assert "api_key=***" in result
        assert "secret123" not in result
        assert "name='test'" in result

    def test_skips_self(self):
        def func(self, x):
            pass
        result = _format_params(func, ("instance", 42), {})
        assert "self" not in result
        assert "x=42" in result

    def test_long_string_truncated(self):
        def func(body):
            pass
        long = "x" * 200
        result = _format_params(func, (long,), {})
        assert "..." in result
        assert len(result) < 200


# ── @log_function decorator tests ────────────────────────────────────

class TestLogFunctionDecorator:
    """Tests that verify the decorator logs correctly.

    Mocks the module-level logger so we can inspect what .info() was
    called with — no caplog propagation headaches.
    """

    def test_decorated_function_returns_correctly(self):
        @log_function
        def add(a, b):
            return a + b
        assert add(2, 3) == 5

    def test_decorated_preserves_name(self):
        @log_function
        def my_func():
            pass
        assert my_func.__name__ == "my_func"

    def test_decorated_preserves_docstring(self):
        @log_function
        def my_func():
            """My docstring."""
            pass
        assert my_func.__doc__ == "My docstring."

    def test_decorated_raises_exception(self):
        @log_function
        def fail():
            raise ValueError("test error")
        with pytest.raises(ValueError, match="test error"):
            fail()

    def test_logs_entry_and_exit(self):
        mock_logger = MagicMock()
        with patch.object(logging_utils_module, "logger", mock_logger):
            @log_function
            def greet(name):
                return f"Hello, {name}"
            result = greet("Alice")

        assert result == "Hello, Alice"
        calls = [str(c) for c in mock_logger.info.call_args_list]
        # __qualname__ includes enclosing class/method, e.g. "TestClass.method.<locals>.greet"
        assert any("▶" in c and "greet" in c for c in calls)
        assert any("◀" in c and "greet" in c for c in calls)

    def test_logs_failure(self):
        mock_logger = MagicMock()
        with patch.object(logging_utils_module, "logger", mock_logger):
            @log_function
            def boom():
                raise RuntimeError("kaboom")
            with pytest.raises(RuntimeError):
                boom()

        calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("FAILED" in c for c in calls)

    def test_masks_sensitive_params(self):
        mock_logger = MagicMock()
        with patch.object(logging_utils_module, "logger", mock_logger):
            @log_function
            def connect(api_key, host):
                return True
            connect("super-secret-key", "localhost")

        log_text = " ".join(str(c) for c in mock_logger.info.call_args_list)
        assert "super-secret-key" not in log_text
        assert "api_key=***" in log_text
        assert "localhost" in log_text

    def test_logs_duration(self):
        mock_logger = MagicMock()
        with patch.object(logging_utils_module, "logger", mock_logger):
            @log_function
            def slow():
                time.sleep(0.05)
                return "done"
            slow()

        exit_calls = [str(c) for c in mock_logger.info.call_args_list if "◀" in str(c)]
        assert len(exit_calls) > 0
        assert "s]" in exit_calls[0]
