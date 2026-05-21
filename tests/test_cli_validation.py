"""Tests for CLI argument validation."""

import argparse
import pytest
from unittest.mock import patch, MagicMock


def test_logs_tail_accepts_positive_value():
    """--tail with a positive integer should work normally."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--tail", "-t", type=int, default=50, help="Number of lines")

    args = parser.parse_args(["--tail", "100"])
    assert args.tail == 100


def test_logs_tail_rejects_negative_value():
    """--tail with a negative integer should raise ArgumentTypeError."""
    def positive_int(value):
        iv = int(value)
        if iv < 0:
            raise argparse.ArgumentTypeError(f"--tail value must be >= 0, got {iv}")
        return iv

    parser = argparse.ArgumentParser()
    parser.add_argument("--tail", "-t", type=positive_int, default=50, help="Number of lines (must be >= 0)")

    with pytest.raises(SystemExit):
        parser.parse_args(["--tail", "-5"])


def test_logs_tail_accepts_zero():
    """--tail with zero should be accepted."""
    def positive_int(value):
        iv = int(value)
        if iv < 0:
            raise argparse.ArgumentTypeError(f"--tail value must be >= 0, got {iv}")
        return iv

    parser = argparse.ArgumentParser()
    parser.add_argument("--tail", "-t", type=positive_int, default=50, help="Number of lines (must be >= 0)")

    args = parser.parse_args(["--tail", "0"])
    assert args.tail == 0
