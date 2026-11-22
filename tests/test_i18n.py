import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import display
import i18n


class I18nTest(unittest.TestCase):
    def test_all_languages_have_identical_keys(self):
        base = set(i18n._STRINGS["en"].keys())
        for lang in i18n.SUPPORTED:
            self.assertEqual(set(i18n._STRINGS[lang].keys()), base)
            self.assertEqual(len(i18n.weekdays(lang)), 7)

    def test_norm_fallback(self):
        self.assertEqual(i18n.norm("TR"), "tr")
        self.assertEqual(i18n.norm("de-DE"), "de")
        self.assertEqual(i18n.norm("fr"), "en")
        self.assertEqual(i18n.norm(None), "en")

    def test_all_glyphs_exist_in_bitmap_fonts(self):
        # Every character in every on-device translation must exist in MID & SMALL fonts
        for lang in i18n.SUPPORTED:
            texts = list(i18n._STRINGS[lang].values()) + list(i18n.weekdays(lang))
            for txt in texts:
                for ch in txt:
                    if ch == " ":
                        continue
                    self.assertIn(ch, display.MID.chars, "Missing %r in MID (%s)" % (ch, lang))
                    self.assertIn(ch, display.SMALL.chars, "Missing %r in SMALL (%s)" % (ch, lang))


if __name__ == "__main__":
    unittest.main()
