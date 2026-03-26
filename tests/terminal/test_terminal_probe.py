"""Tests for terminal probe — verifies graceful degradation in non-TTY CI environments."""

from kida.utils.terminal_probe import probe_ambiguous_width


class TestTerminalProbe:
    def test_returns_none_in_non_tty(self):
        # In CI/test environments, there's no TTY, so probe should return None
        result = probe_ambiguous_width()
        assert result is None

    def test_returns_none_with_zero_timeout(self):
        result = probe_ambiguous_width(timeout=0)
        assert result is None

    def test_return_type(self):
        result = probe_ambiguous_width()
        assert result is None or result in (1, 2)
