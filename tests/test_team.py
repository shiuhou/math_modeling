"""Basic existing team-helper behavior; does not start tmux or write task state."""
import argparse
from pathlib import Path
import subprocess
import sys
import unittest

from scripts import team


class TeamChecks(unittest.TestCase):
    def test_task_names_and_boundaries(self):
        for value in ("a", "repo-bootstrap", "q1_data", "x" * 40):
            with self.subTest(value=value):
                self.assertEqual(team.task_id(value), value)
        for value in ("", "x" * 41, "../escape", "task/name", "Two Words", "-flag"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    team.task_id(value)

    def test_subprocess_failure_is_not_hidden(self):
        with self.assertRaisesRegex(team.TeamError, "fixture failure"):
            team.run(sys.executable, "-c", "import sys; sys.exit('fixture failure')")

    def test_unchecked_subprocess_keeps_failure_status(self):
        result = team.run(sys.executable, "-c", "import sys; sys.exit(7)", check=False)
        self.assertEqual(result.returncode, 7)

    def test_cli_rejects_bad_task_before_creating_state(self):
        script = Path(__file__).resolve().parents[1] / "scripts/team.py"
        result = subprocess.run(
            [sys.executable, str(script), "new", "../invalid"],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("任務名稱", result.stderr)


if __name__ == "__main__":
    unittest.main()
