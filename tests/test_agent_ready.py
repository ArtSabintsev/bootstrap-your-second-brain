#!/usr/bin/env python3
"""Structural + unit tests: template is agent-forkable.

Drives real shipped modules (config.py) and asserts required docs/scripts exist
and that every config.example sources.* key is wired in ingest-daily.sh.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import config as brain_config  # noqa: E402


class TestConfigLoader(unittest.TestCase):
    def test_example_loads_and_strips_doc_keys(self):
        example = json.loads((ROOT / "config.example.json").read_text())
        self.assertIn("_fields", example)
        self.assertIn("sources", example)
        # Reloaded CFG must not expose underscore doc keys at top level.
        self.assertNotIn("_fields", brain_config.CFG)
        self.assertNotIn("_comment", brain_config.CFG)
        self.assertIn("identity", brain_config.CFG)
        self.assertIn("sources", brain_config.CFG)

    def test_source_keys_match_example(self):
        example = json.loads((ROOT / "config.example.json").read_text())
        src = {k: v for k, v in example["sources"].items() if not k.startswith("_")}
        self.assertEqual(set(src.keys()), set(brain_config.SOURCE_KEYS))

    def test_source_enabled_cli_and_api(self):
        # True by default in example
        self.assertTrue(brain_config.source_enabled("podcasts"))
        out = subprocess.check_output(
            [sys.executable, str(ROOT / "scripts" / "config.py"), "--source-enabled", "podcasts"],
            text=True,
        ).strip()
        self.assertEqual(out, "true")

    def test_placeholder_identity_on_example(self):
        # When only example is present or config still has Your Name
        name = brain_config.get("identity.name")
        if name in (None, "Your Name"):
            self.assertTrue(brain_config.is_placeholder_identity())


class TestSourcesWiredInIngest(unittest.TestCase):
    def test_each_source_key_has_enable_branch(self):
        text = (ROOT / "scripts" / "ingest-daily.sh").read_text()
        for key in brain_config.SOURCE_KEYS:
            # lib helper call form used by the orchestrator
            pat = rf"brain_source_enabled\s+{re.escape(key)}"
            self.assertRegex(
                text,
                pat,
                msg=f"sources.{key} not gated via brain_source_enabled in ingest-daily.sh",
            )


class TestAgentDocs(unittest.TestCase):
    REQUIRED_FILES = (
        "SETUP.md",
        "TOOLS.md",
        "AGENTS.md",
        "CLAUDE.md",
        "README.md",
        "config.example.json",
        "secrets.example/README.md",
        "scripts/bootstrap.sh",
        "scripts/doctor.sh",
        "scripts/lib.sh",
        "scripts/log.sh",
        "scripts/ingest-daily.sh",
        "Profile/00-overview.md",
        "Profile/working-with-me.md",
        "tools/xtap/README.md",
    )

    def test_required_paths_exist(self):
        for rel in self.REQUIRED_FILES:
            self.assertTrue((ROOT / rel).is_file(), msg=f"missing {rel}")

    def test_setup_authorizes_agents(self):
        setup = (ROOT / "SETUP.md").read_text().lower()
        self.assertIn("for agents", setup)
        self.assertIn("config.json", setup)
        self.assertIn("must not", setup)
        self.assertIn("interview", setup)
        self.assertIn("doctor", setup)
        self.assertIn("push", setup)

    def test_claude_points_at_setup_for_bootstrap(self):
        claude = (ROOT / "CLAUDE.md").read_text().lower()
        self.assertIn("setup.md", claude)
        self.assertIn("bootstrap", claude)
        self.assertIn("profile", claude)

    def test_tools_documents_stack_and_scrapers(self):
        tools = (ROOT / "TOOLS.md").read_text()
        tools_l = tools.lower()
        for needle in (
            "obsidian",
            "claudian",
            "web clipper",
            "clippings",
            "x bookmarks",
            "xtap",
            "goodreads",
            "substack",
            "github",
            "podcasts",
            "youtube likes",
            "how to add a new ingestor",
            "tools/",
        ):
            self.assertIn(needle, tools_l, msg=f"TOOLS.md missing: {needle}")
        self.assertIn("https://github.com/YishenTu/claudian", tools)
        self.assertIn("realclaudian", tools)
        self.assertNotIn("Senundina/claudian", tools)

    def test_readme_claudian_link(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("https://github.com/YishenTu/claudian", readme)
        self.assertIn("realclaudian", readme)
        self.assertNotIn("Senundina/claudian", readme)

    def test_agents_session_and_log_rules(self):
        agents = (ROOT / "AGENTS.md").read_text().lower()
        self.assertIn("session bootstrap", agents)
        self.assertIn("profile/", agents)
        self.assertIn("log/", agents)
        self.assertIn("if asked to bootstrap", agents)


class TestBrowserCookies(unittest.TestCase):
    """yt-dlp cookie browser must come from config.browser, not a hardcoded name."""

    HARDCODED_SCRIPTS = (
        "scripts/youtube_likes/select_candidates.py",
        "scripts/podcasts/enumerate_inrange.py",
        "scripts/podcasts/fetch_transcript.py",
    )

    def test_ytdlp_cookie_args_uses_config_browser(self):
        args = brain_config.ytdlp_cookie_args()
        self.assertEqual(args[0], "--cookies-from-browser")
        self.assertEqual(args[1], brain_config.browser())
        self.assertNotEqual(args[1], "")

    def test_no_hardcoded_brave_cookie_flag_in_ytdlp_scripts(self):
        for rel in self.HARDCODED_SCRIPTS:
            text = (ROOT / rel).read_text()
            self.assertNotRegex(
                text,
                r'["\']--cookies-from-browser["\']\s*,\s*["\']brave["\']',
                msg=f"{rel} still hardcodes brave cookies",
            )
            self.assertIn("ytdlp_cookie_args", text, msg=f"{rel} must call ytdlp_cookie_args()")

    def test_tools_claims_browser_drives_ytdlp(self):
        tools = (ROOT / "TOOLS.md").read_text().lower()
        self.assertIn("yt-dlp", tools)
        self.assertIn("config.browser", tools.replace("`", "").replace(" ", "") or tools)
        # either form
        self.assertTrue(
            "config.browser" in (ROOT / "TOOLS.md").read_text()
            or "config.json" in tools and "yt-dlp" in tools
        )


class TestShellSyntax(unittest.TestCase):
    SCRIPTS = (
        "scripts/bootstrap.sh",
        "scripts/doctor.sh",
        "scripts/ingest-daily.sh",
        "scripts/lib.sh",
        "scripts/log.sh",
        "scripts/ask.sh",
        "scripts/intelligence/brief.sh",
        "scripts/sources/x-bookmarks.sh",
        "scripts/podcasts/backfill.sh",
        "scripts/youtube_likes/run.sh",
    )

    def test_bash_n(self):
        for rel in self.SCRIPTS:
            path = ROOT / rel
            if not path.is_file():
                self.fail(f"missing {rel}")
            r = subprocess.run(
                ["bash", "-n", str(path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, msg=f"bash -n {rel}: {r.stderr}")


if __name__ == "__main__":
    unittest.main()
