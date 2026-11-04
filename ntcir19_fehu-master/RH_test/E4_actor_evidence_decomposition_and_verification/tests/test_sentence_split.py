import json
import os
import unittest

import context  # noqa: F401
from sentence_split import (render_numbered, split_sentences, verify_split,
                            visible_sids)


class TestSentenceSplit(unittest.TestCase):
    def test_basic_split_and_ids(self):
        sents = split_sentences("One sentence. Another one! A third? Done.")
        self.assertEqual([s["sid"] for s in sents], ["S1", "S2", "S3", "S4"])
        self.assertEqual(sents[0]["text"], "One sentence.")
        self.assertEqual(sents[1]["text"], "Another one!")

    def test_traceability_exact_substrings(self):
        content = "  First.  \n\nSecond one here. Third.\n"
        sents = split_sentences(content)
        for s in sents:
            self.assertEqual(content[s["start"]:s["end"]], s["text"])

    def test_determinism(self):
        content = "A test. Another test. “Quoted.” Done."
        self.assertEqual(split_sentences(content), split_sentences(content))

    def test_abbreviations_and_initials_not_split(self):
        sents = split_sentences("Mr. Smith met Dr. Jones. J. Doe agreed.")
        self.assertEqual([s["text"] for s in sents],
                         ["Mr. Smith met Dr. Jones.", "J. Doe agreed."])

    def test_newlines_are_hard_boundaries(self):
        sents = split_sentences("no terminal punctuation\nsecond line")
        self.assertEqual(len(sents), 2)

    def test_closing_quote_stays_with_sentence(self):
        sents = split_sentences('“Stop now.” He left.')
        self.assertEqual(sents[0]["text"], '“Stop now.”')
        self.assertEqual(sents[1]["text"], "He left.")

    def test_verify_split_rejects_tampering(self):
        content = "One. Two."
        sents = split_sentences(content)
        sents[0]["text"] = "One!"
        with self.assertRaises(Exception):
            verify_split(content, sents)

    def test_real_dev_articles_roundtrip(self):
        """Every dev article splits with full traceability + coverage."""
        base = os.path.dirname(os.path.dirname(context.E4_DIR))
        dev_path = os.path.join(base, "dataset", "dev", "dev_event_base.json")
        with open(dev_path, "r", encoding="utf-8") as f:
            articles = json.load(f)
        self.assertGreater(len(articles), 0)
        for article in articles:
            sents = split_sentences(article["content"])  # verify_split inside
            self.assertGreater(len(sents), 0, article["guid"])

    def test_visible_sids_short_article(self):
        content = "One. Two."
        sents = split_sentences(content)
        self.assertEqual(visible_sids(content, sents),
                         [s["sid"] for s in sents])

    def test_visible_sids_long_article_truncates_middle(self):
        content = "\n".join(f"Sentence number {i} is here." for i in range(700))
        self.assertGreater(len(content), 12000)
        sents = split_sentences(content)
        vis = visible_sids(content, sents)
        self.assertLess(len(vis), len(sents))
        self.assertIn("S1", vis)
        self.assertIn(sents[-1]["sid"], vis)
        rendered = render_numbered(sents, vis)
        self.assertIn("...[sentences omitted]...", rendered)
        # global IDs preserved for the tail sentences
        self.assertIn(f"{sents[-1]['sid']}: {sents[-1]['text']}", rendered)

    def test_render_numbered_full(self):
        sents = split_sentences("One. Two.")
        self.assertEqual(render_numbered(sents), "S1: One.\nS2: Two.")


if __name__ == "__main__":
    unittest.main()
