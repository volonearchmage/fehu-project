"""Focused checks for cross-platform archive references and score comparison."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

import verify_offline as verifier


class OfflineVerificationTests(unittest.TestCase):
    def test_windows_and_posix_references_resolve_equally(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = (root / "dataset" / "dev" / "input.json").resolve()
            self.assertEqual(verifier.contained_path(root, "dataset\\dev\\input.json"), expected)
            self.assertEqual(verifier.contained_path(root, "dataset/dev/input.json"), expected)

    def test_archive_paths_reject_absolute_and_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            for reference in ("../key", "folder\\..\\key", "/tmp/key", "C:\\key",
                              "C:key", "\\\\server\\share\\key", "folder//key", "file:stream", ""):
                with self.subTest(reference=reference), self.assertRaises(ValueError):
                    verifier.contained_path(directory, reference)

    def test_archive_paths_reject_symlink_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "archive"
            root.mkdir()
            link = root / "outside"
            try:
                link.symlink_to(Path(directory), target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"Symlinks unavailable: {exc.__class__.__name__}")
            with self.assertRaises(ValueError):
                verifier.contained_path(root, "outside/private.json")

    def test_nested_comparison_accepts_only_roundoff(self):
        verifier.compare_json({"scores": [{"f1": 0.27903715821453606, "count": 508}]},
                              {"scores": [{"f1": 0.2790371582145361, "count": 508}]})
        with self.assertRaises(ValueError):
            verifier.compare_json({"f1": 0.27903715821453606}, {"f1": 0.28})

    def test_nested_comparison_rejects_shape_type_and_nonfinite_changes(self):
        pairs = [({"score": 1}, {"score": True}), ({"score": 1}, {"score": 1, "extra": 0}),
                 ([1], [1, 2]), ({"ok": True}, {"ok": 1}), ({"score": float("nan")}, {"score": float("nan")})]
        for expected, actual in pairs:
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                verifier.compare_json(expected, actual)

    def test_output_cannot_overwrite_historical_archive(self):
        with contextlib.redirect_stderr(io.StringIO()):
            code = verifier.main(["--out", str(verifier.HERE / "subset_evaluation_completed")])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
