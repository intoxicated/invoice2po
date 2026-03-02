"""
Tests for JSON adjustment logic (json_adjust). No LangChain — safe to run in isolation.
"""

import json
import unittest

from json_adjust import extract_json, fix_json, repair_truncated_json


class TestFixJson(unittest.TestCase):
    """Test fix_json — trailing comma removal."""

    def test_trailing_comma_before_brace(self):
        raw = '{"a": 1, "b": 2,}'
        result = fix_json(raw)
        self.assertEqual(json.loads(result), {"a": 1, "b": 2})

    def test_trailing_comma_before_bracket(self):
        raw = '{"a": [1, 2,]}'
        result = fix_json(raw)
        self.assertEqual(json.loads(result), {"a": [1, 2]})

    def test_multiple_trailing_commas(self):
        raw = '{"x": {"a": [1,],},}'
        result = fix_json(raw)
        self.assertEqual(json.loads(result), {"x": {"a": [1]}})

    def test_valid_json_unchanged(self):
        raw = '{"a": 1, "b": "x"}'
        result = fix_json(raw)
        self.assertEqual(json.loads(result), {"a": 1, "b": "x"})


class TestRepairTruncatedJson(unittest.TestCase):
    """Test repair_truncated_json — truncation repair."""

    def test_truncation_after_colon(self):
        raw = '{"vendor_notation": '
        result = repair_truncated_json(raw)
        self.assertEqual(json.loads(result), {"vendor_notation": None})

    def test_truncation_after_colon_space(self):
        raw = '{"key":  '
        result = repair_truncated_json(raw)
        self.assertEqual(json.loads(result), {"key": None})

    def test_truncation_after_opening_quote(self):
        raw = '{"key": "'
        result = repair_truncated_json(raw)
        self.assertEqual(json.loads(result), {"key": ""})

    def test_truncation_inside_string(self):
        raw = '{"matched_product_name": "AMP'
        result = repair_truncated_json(raw)
        self.assertEqual(json.loads(result), {"matched_product_name": "AMP"})

    def test_truncation_inside_long_string(self):
        raw = '{"vendor_notation": "IVE - THE 2ND ALBUM [REVIVE+] (LOVED IVE ver.)", "matched_product_name": "IVE - REVIVE+ (2ND ALBUM'
        result = repair_truncated_json(raw)
        parsed = json.loads(result)
        self.assertEqual(parsed["vendor_notation"], "IVE - THE 2ND ALBUM [REVIVE+] (LOVED IVE ver.)")
        self.assertEqual(parsed["matched_product_name"], "IVE - REVIVE+ (2ND ALBUM")

    def test_truncation_missing_closing_brace_only(self):
        raw = '{"a": 1, "b": "x"'
        result = repair_truncated_json(raw)
        self.assertEqual(json.loads(result), {"a": 1, "b": "x"})

    def test_truncation_trailing_comma_then_brace(self):
        raw = '{"a": 1, '
        result = repair_truncated_json(raw)
        self.assertEqual(json.loads(result), {"a": 1})

    def test_truncation_nested_object(self):
        raw = '{"outer": {"inner": "val'
        result = repair_truncated_json(raw)
        self.assertEqual(json.loads(result), {"outer": {"inner": "val"}})

    def test_truncation_array(self):
        raw = '{"entries": [{"sku": "X", "name": "Prod'
        result = repair_truncated_json(raw)
        parsed = json.loads(result)
        self.assertEqual(parsed["entries"], [{"sku": "X", "name": "Prod"}])

    def test_complete_number_at_end_no_string_close(self):
        raw = '{"quantity": 8'
        result = repair_truncated_json(raw)
        self.assertEqual(json.loads(result), {"quantity": 8})

    def test_empty_object_truncated(self):
        raw = '{'
        result = repair_truncated_json(raw)
        self.assertEqual(json.loads(result), {})

    def test_string_with_special_chars(self):
        raw = '{"sku": "AMPERS&ONE-LOUD & PROUD'
        result = repair_truncated_json(raw)
        self.assertEqual(json.loads(result), {"sku": "AMPERS&ONE-LOUD & PROUD"})

    def test_already_complete_json(self):
        raw = '{"a": 1}'
        result = repair_truncated_json(raw)
        self.assertEqual(json.loads(result), {"a": 1})

    def test_number_followed_by_space_no_string_close(self):
        """Trailing space after number should not trigger string-close (bug fix)."""
        raw = '{"quantity": 8 '
        result = repair_truncated_json(raw)
        self.assertEqual(json.loads(result), {"quantity": 8})


class TestExtractJson(unittest.TestCase):
    """Test extract_json — full extraction pipeline."""

    def test_plain_json(self):
        text = '{"vendor_notation": "X", "matched_sku": "Y"}'
        result = extract_json(text)
        self.assertEqual(result["vendor_notation"], "X")
        self.assertEqual(result["matched_sku"], "Y")

    def test_json_in_code_block(self):
        text = '```json\n{"a": 1}\n```'
        result = extract_json(text)
        self.assertEqual(result, {"a": 1})

    def test_json_in_code_block_no_lang(self):
        text = '```\n{"a": 1}\n```'
        result = extract_json(text)
        self.assertEqual(result, {"a": 1})

    def test_text_before_and_after_json(self):
        text = 'Here is the result:\n\n{"a": 1}\n\nDone.'
        result = extract_json(text)
        self.assertEqual(result, {"a": 1})

    def test_trailing_comma_parsed_via_fix(self):
        text = '{"vendor_notation": "X",}'
        result = extract_json(text)
        self.assertEqual(result["vendor_notation"], "X")

    def test_truncated_json_repaired(self):
        text = '{"vendor_notation": "AMPERS&ONE - 3rd Mini Album", "matched_product_name": "AMP'
        result = extract_json(text)
        self.assertEqual(result["vendor_notation"], "AMPERS&ONE - 3rd Mini Album")
        self.assertEqual(result["matched_product_name"], "AMP")

    def test_truncated_after_colon_repaired(self):
        text = '{"vendor_notation": '
        result = extract_json(text)
        self.assertEqual(result["vendor_notation"], None)

    def test_full_catalog_structure(self):
        text = '''{
          "vendor_notation": "IVE - REVIVE+ (LOVED IVE ver.)",
          "matched_sku": "IVE-REVIVE+-LOVEDIVEVER",
          "matched_product_name": "IVE - REVIVE+ (2ND ALBUM)",
          "standard_product_id": "std_product_abc123",
          "confidence": 0.95,
          "catalog_entries": [
            {"sku": "IVE-REVIVE+-LOVEDIVEVER", "variant_name": "", "is_invoice_item": true}
          ]
        }'''
        result = extract_json(text)
        self.assertEqual(result["vendor_notation"], "IVE - REVIVE+ (LOVED IVE ver.)")
        self.assertEqual(len(result["catalog_entries"]), 1)
        self.assertTrue(result["catalog_entries"][0]["is_invoice_item"])

    def test_full_catalog_with_trailing_comma(self):
        text = '''{
          "vendor_notation": "X",
          "catalog_entries": [{"sku": "Y", "is_invoice_item": true},]
        }'''
        result = extract_json(text)
        self.assertEqual(len(result["catalog_entries"]), 1)
        self.assertEqual(result["catalog_entries"][0]["sku"], "Y")

    def test_no_json_raises(self):
        with self.assertRaises(ValueError) as ctx:
            extract_json("No JSON here at all")
        self.assertIn("No JSON", str(ctx.exception))

    def test_truncated_fallback_extracts_matched_sku(self):
        """When JSON is truncated and unparseable, fallback extracts matched_sku via regex."""
        text = '{"vendor_notation": "NCT JNJM...", "matched_sku": "NCT JNJM-BOTH SIDES-POSTER VER", "matched_produc'
        result = extract_json(text, vendor_notation="NCT JNJM - 1ST MINI ALBUM")
        self.assertEqual(result["matched_sku"], "NCT JNJM-BOTH SIDES-POSTER VER")
        self.assertEqual(result["confidence"], 0.5)
        self.assertEqual(len(result["catalog_entries"]), 1)
        self.assertTrue(result["catalog_entries"][0]["is_invoice_item"])


if __name__ == "__main__":
    unittest.main()
