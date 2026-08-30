import unittest

from bot.formatting import split_message


class SplitMessageTests(unittest.TestCase):
    def test_short_text_untouched(self):
        self.assertEqual(split_message("hola"), ["hola"])

    def test_empty_and_whitespace(self):
        self.assertEqual(split_message(""), [])
        self.assertEqual(split_message("   \n  "), [])

    def test_all_parts_within_limit(self):
        text = "\n\n".join(f"Párrafo {i} " + "x" * 200 for i in range(20))
        parts = split_message(text, limit=500)
        self.assertTrue(all(len(p) <= 500 for p in parts))
        self.assertGreater(len(parts), 1)

    def test_no_word_split_on_space_boundary(self):
        text = "palabra " * 100  # 800 chars, sin saltos de línea
        parts = split_message(text, limit=100)
        for p in parts:
            self.assertNotIn("  ", p)
            for token in p.split():
                self.assertEqual(token, "palabra")

    def test_hard_cut_when_no_boundary(self):
        text = "a" * 250
        parts = split_message(text, limit=100)
        self.assertEqual(parts, ["a" * 100, "a" * 100, "a" * 50])

    def test_prefers_paragraph_over_line_boundary(self):
        text = "uno\ndos\n\ntres cuatro cinco"
        parts = split_message(text, limit=12)
        self.assertEqual(parts[0], "uno\ndos")

    def test_content_preserved_ignoring_whitespace(self):
        text = "  ".join(f"frase{i}" for i in range(300))
        parts = split_message(text, limit=200)
        self.assertEqual(
            " ".join(parts).split(),
            text.split(),
        )

    def test_invalid_limit(self):
        with self.assertRaises(ValueError):
            split_message("x", limit=0)


if __name__ == "__main__":
    unittest.main()
