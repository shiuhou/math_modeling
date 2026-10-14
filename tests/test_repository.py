"""Repository-tool fixtures only: no competition data or research experiments."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import check_repo


REPO = Path(__file__).resolve().parents[1]


class RepositoryChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def errors(self):
        return check_repo.check_files(self.root, check_repo.repository_files(self.root))

    def cli(self):
        return subprocess.run(
            [sys.executable, str(REPO / "scripts/check_repo.py"), "--root", str(self.root)],
            text=True, capture_output=True,
        )

    def test_valid_local_links_directories_and_json(self):
        self.write("docs/topic.md", "# Topic\n")
        self.write("docs/two words(1).md", "# Topic\n")
        self.write("sample.json", '{"kind": "example", "measured": null}\n')
        self.write("README.md", '\n'.join([
            '[file](docs/topic.md#topic)', '[directory](docs/)',
            '[space](docs/two%20words%281%29.md)',
            '[angle](<docs/two words(1).md>)', '[title](docs/topic.md "Topic")',
            '[remote](https://example.invalid/not-contacted)', '[anchor](#local)',
        ]))
        self.assertEqual(self.errors(), [])
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS:", result.stdout)

    def test_missing_link_reports_location_and_fails_cli(self):
        self.write("README.md", "# Title\n\n[missing](missing.md)\n")
        self.assertEqual(len(self.errors()), 1)
        self.assertIn("README.md:3", self.errors()[0])
        result = self.cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing.md", result.stderr)
        self.assertNotIn("PASS:", result.stdout)

    def test_existing_ignored_target_is_not_a_portable_link(self):
        self.write(".gitignore", "private/\n")
        self.write("private/data.md", "# Ignored\n")
        self.write("README.md", "[file](private/data.md)\n[dir](private/)\n")
        self.assertEqual(len(self.errors()), 2)
        self.assertTrue(all("ignored" in error for error in self.errors()))

    def test_links_outside_repository_and_absolute_paths_fail(self):
        self.write("README.md", "[outside](../elsewhere.md)\n[absolute](/etc/hosts)\n")
        self.assertEqual(len(self.errors()), 2)
        self.assertTrue(all("leaves repository" in error for error in self.errors()))

    def test_code_examples_are_not_links(self):
        self.write("README.md", "\n".join([
            '```md', '[example](missing.md)', '```',
            '~~~md', '[example](missing.md)', '~~~',
            '`[example](missing.md)`', '    [example](missing.md)',
        ]))
        self.assertEqual(self.errors(), [])

    def test_invalid_json_and_ambiguous_values_fail(self):
        cases = ['{"a": }', '{"a": 1, "a": 2}', '{"a": NaN}', '{"a": Infinity}']
        for content in cases:
            with self.subTest(content=content):
                self.write("fixture.json", content)
                errors = self.errors()
                self.assertEqual(len(errors), 1)
                self.assertIn("fixture.json:", errors[0])
        result = self.cli()
        self.assertEqual(result.returncode, 1)

    def test_non_repository_fails_instead_of_reporting_success(self):
        empty = self.root / "not-a-repository"
        empty.mkdir()
        # Use a directory outside the fixture repository to avoid Git's parent lookup.
        with tempfile.TemporaryDirectory() as other:
            result = subprocess.run(
                [sys.executable, str(REPO / "scripts/check_repo.py"), "--root", other],
                text=True, capture_output=True,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("unable to inspect repository", result.stderr)

    def test_ignore_rules_keep_formal_evidence_and_hide_local_inputs(self):
        self.write(".gitignore", (REPO / ".gitignore").read_text(encoding="utf-8"))
        ignored = {
            ".env", ".env.local", "auth.json", ".codex/auth.json", "key.pem",
            ".venv/lib/site.py", "__pycache__/cache.pyc",
            "data/raw.csv", "data/private.json", "outputs/run/solver.log",
        }
        retained = {
            ".env.example", "data/README.md", "outputs/README.md",
            "results/run/manifest.json", "results/run/metrics.csv",
            "results/run/detail.json", "results/run/solver.log",
            "results/run/report.pdf", "paper/report.pdf", "figures/chart.pdf",
            "modeling.md", "codex_repo_bootstrap_prompt.md",
        }
        result = subprocess.run(
            ["git", "-c", "core.excludesFile=/dev/null", "check-ignore", "--no-index", "-z", "--stdin"],
            cwd=self.root, input="\0".join(sorted(ignored | retained)) + "\0",
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(result.stdout.rstrip("\0").split("\0")), ignored)


if __name__ == "__main__":
    unittest.main()
