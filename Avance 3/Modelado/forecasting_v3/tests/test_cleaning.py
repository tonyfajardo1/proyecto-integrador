from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quickbooks_forecast.cleaning import extract_product_code, normalize_product_name


class CleaningTests(unittest.TestCase):
    def test_normalize_product_name_removes_signs_and_accents(self) -> None:
        self.assertEqual(
            normalize_product_name("* ALIÑO FDA 90 GRS. (4488)"),
            "ALINO FDA 90 GRS 4488",
        )

    def test_extract_product_code_prefers_parentheses(self) -> None:
        self.assertEqual(extract_product_code("* ALINO FDA 90 GRS (4488)"), "4488")


if __name__ == "__main__":
    unittest.main()
