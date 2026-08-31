import unittest

from bot.config import _parse_chat_ids


class ParseChatIdsTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(_parse_chat_ids(None), frozenset())
        self.assertEqual(_parse_chat_ids(""), frozenset())
        self.assertEqual(_parse_chat_ids("  ,  "), frozenset())

    def test_single(self):
        self.assertEqual(_parse_chat_ids("123"), frozenset({123}))

    def test_multiple_with_spaces_and_trailing_comma(self):
        self.assertEqual(_parse_chat_ids(" 123 , 456 ,"), frozenset({123, 456}))

    def test_negative_id(self):
        self.assertEqual(_parse_chat_ids("-1001234"), frozenset({-1001234}))

    def test_non_numeric_raises(self):
        with self.assertRaises(ValueError):
            _parse_chat_ids("123,abc")


if __name__ == "__main__":
    unittest.main()
