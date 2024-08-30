from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_PATH = Path(os.path.realpath(__file__)).parents[2]
LOGGER = logging.getLogger(__name__)
console_handler = logging.StreamHandler()

LOGGER.addHandler(console_handler)
LOGGER.setLevel(logging.DEBUG)


def get_previous_version(file_path):
    try:
        result = subprocess.run(
            ["git", "log", "-p", "-n 1", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            LOGGER.error("Error reading git log:", result.stderr)
            return None

        # Look for the previous version in the diff
        diff_content = result.stdout
        match = re.search(r'\+__version__\s*=\s*["\']([^"\']+)["\']', diff_content)
        if match:
            return match.group(1)
        return None
    except Exception as e:
        LOGGER.error(f"Exception occurred: {e}")
        return None


def get_current_version(file_path):
    try:
        with open(file_path, "r") as f:
            content = f.read()
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
        return None
    except Exception as e:
        LOGGER.error(f"Exception occurred: {e}")
        return None


def check_git_diff(file_path):
    try:
        result = subprocess.run(
            ["git", "diff", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            LOGGER.error("Error running git diff:", result.stderr)
            return False

        # If there's any output from git diff, it means there are changes
        diff_output = result.stdout
        LOGGER.info(f"Diff output = {diff_output}")
        if diff_output:
            return True
        LOGGER.error("reererergf")
        return False
    except Exception as e:
        LOGGER.error(f"Exception occurred while checking git diff: {e}")
        return False


def main():
    version_file_path = os.path.join(f"{DEFAULT_PATH}/jira_telegram_bot", "__init__.py")

    current_version = get_current_version(version_file_path)
    if not current_version:
        LOGGER.info(f"Could not find current version in {version_file_path}")
        return 0

    previous_version = get_previous_version(version_file_path)
    if not previous_version:
        LOGGER.info(
            f"Could not find previous version in git log for {version_file_path}",
        )
        return 0

    if current_version <= previous_version:
        LOGGER.info(
            f"Version in {version_file_path} has not been updated. Previous version: {previous_version},"
            f" Current version: {current_version}",
        )
        return 0

    LOGGER.info(
        f"Version updated successfully. Previous version: {previous_version}, Current version: {current_version}",
    )
    return 1


if __name__ == "__main__":
    if main() == 1:
        sys.exit(0)
    else:
        sys.exit(1)
