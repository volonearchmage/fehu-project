import unittest

import context  # noqa: F401
import freeze_check


class TestFrozenUnchanged(unittest.TestCase):
    def test_e1_e2_e3_e3a_liu_files_unchanged(self):
        """E1/E2/E3/E3a and the Liu pipeline match the snapshot taken when
        E4 was built (config/frozen_hashes.json)."""
        missing, changed, _added = freeze_check.compare()
        self.assertEqual(missing, [], f"frozen files deleted: {missing}")
        self.assertEqual(changed, [], f"frozen files modified: {changed}")

    def test_snapshot_covers_all_four_experiments(self):
        hashes = freeze_check.compute_hashes()
        for marker in ("E1_fewshot_repair", "E2_prompt_bias_control",
                       "E3_subevent_decomposition", "E3a_task1_only_subevent",
                       "liu_method"):
            self.assertTrue(any(marker in p for p in hashes),
                            f"no frozen files hashed under {marker}")


if __name__ == "__main__":
    unittest.main()
