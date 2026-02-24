"""Unit tests for release version filtering at the repository parse level."""
from __future__ import annotations

import unittest

from jira_telegram_bot.entities.synth_pm.constants import RELEASE_VERSION_PATTERN


class TestReleaseVersionPattern(unittest.TestCase):
    """Test that RELEASE_VERSION_PATTERN accepts only xx.xx.xx format."""

    def test_valid_versions_match(self):
        """Numeric two-digit triplets separated by dots should match."""
        valid = ["04.12.01", "00.00.00", "99.99.99", "01.02.03"]
        for version in valid:
            self.assertIsNotNone(
                RELEASE_VERSION_PATTERN.match(version),
                f"{version!r} should be a valid release version",
            )

    def test_invalid_versions_do_not_match(self):
        """Non-conforming strings should be rejected."""
        invalid = [
            "Version 2.5.0",
            "1.2.3",
            "04.12",
            "04.12.001",
            "v04.12.01",
            "abc",
            "",
            " ",
            "04-12-01",
            "Sprint 10",
            "my-release",
            "Feature XYZ",
        ]
        for version in invalid:
            self.assertIsNone(
                RELEASE_VERSION_PATTERN.match(version.strip()),
                f"{version!r} should NOT be a valid release version",
            )


class TestRepositoryReleaseFiltering(unittest.TestCase):
    """Test that repository parsers set release=None for invalid values.

    These tests verify the filtering logic inline without instantiating
    the full repository (which requires many dependencies).  The pattern
    check is identical to the one used in
    ``_parse_row_to_feature_with_mapping``.
    """

    @staticmethod
    def _filter_release(raw_value: str) -> str | None:
        """Mimic the repository parse-time release filter."""
        if (
            raw_value not in ("Select", "")
            and RELEASE_VERSION_PATTERN.match(raw_value.strip())
        ):
            return raw_value
        return None

    def test_valid_release_is_kept(self):
        """A proper xx.xx.xx value passes through."""
        self.assertEqual(self._filter_release("04.12.01"), "04.12.01")

    def test_feature_name_is_rejected(self):
        """A feature/story name is filtered to None."""
        self.assertIsNone(self._filter_release("Feature XYZ"))

    def test_semver_is_rejected(self):
        """A semver-style version like 2.5.0 is filtered to None."""
        self.assertIsNone(self._filter_release("Version 2.5.0"))

    def test_empty_string_is_rejected(self):
        """Empty string is filtered to None."""
        self.assertIsNone(self._filter_release(""))

    def test_select_placeholder_is_rejected(self):
        """'Select' placeholder is filtered to None."""
        self.assertIsNone(self._filter_release("Select"))


if __name__ == "__main__":
    unittest.main()
