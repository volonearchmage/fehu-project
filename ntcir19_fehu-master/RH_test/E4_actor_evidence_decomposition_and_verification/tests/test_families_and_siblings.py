import unittest

import context  # noqa: F401
from e4_common import (DIRECTIONS, Taxonomy, load_families, load_frozen_e1,
                       load_sibling_map)
from family_scan import contrast_value_block, family_value_block


class TestFamiliesAndSiblings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e1 = load_frozen_e1()
        cls.taxonomy = Taxonomy(cls.e1)
        cls.families = load_families(cls.taxonomy)
        cls.siblings = load_sibling_map(cls.taxonomy)

    def test_all_54_l1_and_108_directed_classes_valid(self):
        self.assertEqual(len(self.taxonomy.l1_id_to_name), 54)
        self.assertEqual(sorted(self.taxonomy.l1_id_to_name, key=int),
                         [str(i) for i in range(54)])
        directed = {(l1, d) for l1 in self.taxonomy.l1_id_to_name
                    for d in DIRECTIONS}
        self.assertEqual(len(directed), 108)
        # every L1 maps to a valid L2 (official mapping complete)
        for l1 in self.taxonomy.l1_id_to_name:
            self.assertIn(self.taxonomy.l1_id_to_l2_id[l1],
                          self.taxonomy.l2_id_to_name)

    def test_families_partition_taxonomy(self):
        """load_families already hard-validates; re-assert key properties."""
        covered = [l1 for f in self.families for l1 in f["l1_ids"]]
        self.assertEqual(sorted(covered, key=int), [str(i) for i in range(54)])
        self.assertEqual(len(covered), len(set(covered)),
                         "an L1 value is scanned by two families")
        self.assertLessEqual(len(self.families), 6,
                             "families must stay a small number")

    def test_contrast_values_never_assignable(self):
        for fam in self.families:
            contrast_l1 = {l1 for l2 in fam["contrast_l2_ids"]
                           for l1 in self.taxonomy.l1_ids_by_l2[l2]}
            self.assertFalse(contrast_l1 & set(fam["l1_ids"]))

    def test_family_prompt_blocks_complete(self):
        for fam in self.families:
            block = family_value_block(fam, self.taxonomy)
            for l1 in fam["l1_ids"]:
                self.assertIn(
                    f"{l1}: {self.taxonomy.l1_id_to_name[l1]}", block)
            contrast = contrast_value_block(fam, self.taxonomy)
            for l2 in fam["contrast_l2_ids"]:
                self.assertIn(self.taxonomy.l2_id_to_name[l2], contrast)

    def test_sibling_map_valid_symmetric_complete(self):
        self.assertEqual(set(self.siblings), set(self.taxonomy.l1_id_to_name))
        for l1, sibs in self.siblings.items():
            self.assertNotIn(l1, sibs, f"{l1} is its own sibling")
            for sib in sibs:
                self.assertTrue(self.taxonomy.valid_l1(sib))
                self.assertIn(l1, self.siblings[sib],
                              f"sibling map not symmetric: {l1}<->{sib}")

    def test_same_l2_values_are_always_siblings(self):
        for l2, l1_ids in self.taxonomy.l1_ids_by_l2.items():
            for a in l1_ids:
                for b in l1_ids:
                    if a != b:
                        self.assertIn(b, self.siblings[a])

    def test_curated_cross_l2_pairs_present(self):
        self.assertIn("42", self.siblings["37"])  # helpful <-> responsible
        self.assertIn("46", self.siblings["26"])  # safe country <-> world peace


if __name__ == "__main__":
    unittest.main()
