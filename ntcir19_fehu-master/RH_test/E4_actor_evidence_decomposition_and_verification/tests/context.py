"""Shared test setup: puts implementation/ on sys.path. Import this first."""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
E4_DIR = os.path.dirname(TESTS_DIR)
IMPL_DIR = os.path.join(E4_DIR, "implementation")
if IMPL_DIR not in sys.path:
    sys.path.insert(0, IMPL_DIR)

os.environ.setdefault("E1_RUN_TS", "e4_offline_test_noop")


def synthetic_article():
    """A small article with two actors and predictable sentences."""
    content = ("Police arrested the smuggler on Monday. "
               "The smuggler had sold unsafe fuel to families.\n\n"
               "“We will protect the public,” said Chief Rivera. "
               "Residents praised the quick response.")
    return {
        "guid": "e4-test-0001",
        "title": "Police arrest fuel smuggler",
        "content": content,
        "actors": [{"Police": "A-police"}, {"The smuggler": "A-smuggler"}],
    }
