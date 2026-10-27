#!/usr/bin/env python3
"""Test suite for the Night Shift Survival Guide build.

Runs the real build script into a temporary directory and verifies the
generated site: page inventory, structure, link integrity, anchors, and
local-first guarantees (no external references, no scripts).

Run: python3 -m unittest discover -s tests -v
"""

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import build as build_mod

EXPECTED_PAGES = [
    "index.html",
    "introduction.html",
    "sleep-window-planning.html",
    "daytime-sleep-environment.html",
    "light-and-caffeine-timing.html",
    "meals-and-snacks.html",
    "driving-home-safety.html",
    "family-boundary-scripts.html",
    "low-energy-recovery-day.html",
    "shift-cycle-planner.html",
    "glossary.html",
    "styles.css",
]


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = []
        self.scripts = []
        self.external = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "script":
            self.scripts.append(attrs.get("src", ""))


def collect(page_html):
    parser = LinkCollector()
    parser.feed(page_html)
    return parser


class TestParser(unittest.TestCase):
    def test_inline_formatting(self):
        html_out = build_mod.render_inline(
            "**bold** and *ital* and `code` and [text](01-x.md#frag)"
        )
        self.assertIn("<strong>bold</strong>", html_out)
        self.assertIn("<em>ital</em>", html_out)
        self.assertIn("<code>code</code>", html_out)
        self.assertIn('href="x.html#frag"', html_out)

    def test_asterisk_in_prose_is_not_emphasis(self):
        html_out = build_mod.render_inline("protein * fiber + carbs")
        self.assertEqual(html_out, "protein * fiber + carbs")

    def test_html_is_escaped(self):
        html_out = build_mod.render_inline("a < b & c > d")
        self.assertNotIn("< b", html_out)
        self.assertIn("&amp;", html_out)

    def test_heading_ids(self):
        html_out = build_mod.render_markdown("# The Big Idea\n\n## The big idea\n")
        self.assertIn('id="the-big-idea"', html_out)
        self.assertIn('id="the-big-idea-2"', html_out)

    def test_nested_lists(self):
        html_out = build_mod.render_markdown("- a\n  - b\n    - c\n- d\n")
        self.assertEqual(
            html_out,
            "<ul><li>a<ul><li>b<ul><li>c</li></ul></li></ul></li><li>d</li></ul>",
        )

    def test_task_lists(self):
        html_out = build_mod.render_markdown("- [ ] todo\n- [x] done\n")
        self.assertIn('<li class="task"><input type="checkbox"> todo</li>', html_out)
        self.assertIn(
            '<li class="task"><input type="checkbox" checked> done</li>', html_out
        )

    def test_table(self):
        html_out = build_mod.render_markdown(
            "| A | B |\n| --- | :---: |\n| 1 | 2 |\n"
        )
        self.assertIn("<table>", html_out)
        self.assertIn('style="text-align:center"', html_out)
        self.assertIn("<td>1</td>", html_out)

    def test_blockquote_and_hr(self):
        html_out = build_mod.render_markdown("> line one\n> line two\n\n---\n")
        self.assertIn("<blockquote>", html_out)
        self.assertIn("<hr>", html_out)

    def test_continuation_lines_join(self):
        html_out = build_mod.render_markdown(
            "* start with **bold marker**\n  and closing on next line\n"
        )
        self.assertIn("<strong>bold marker</strong>", html_out)
        self.assertNotIn("**", html_out)


class TestSiteBuild(unittest.TestCase):
    out_dir = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="nssg-test-")
        cls.out_dir = Path(cls.tmp) / "site"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "build.py"), "--out", str(cls.out_dir)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"build failed: {proc.stderr}"
        cls.pages = {
            p.name: p.read_text(encoding="utf-8") for p in cls.out_dir.glob("*.html")
        }

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_expected_files_exist(self):
        for name in EXPECTED_PAGES:
            self.assertTrue((self.out_dir / name).exists(), f"missing {name}")

    def test_every_page_has_chrome(self):
        for name, html_out in self.pages.items():
            with self.subTest(page=name):
                self.assertIn("<!DOCTYPE html>", html_out)
                self.assertIn('<meta charset="utf-8">', html_out)
                self.assertIn("Night Shift Survival Guide", html_out)
                self.assertIn("not medical advice", html_out)
                self.assertIn("2026 Asdale Dynamics, LLC", html_out)
                self.assertNotIn("{{", html_out), f"template placeholder in {name}"

    def test_chapters_have_h1_and_nav_current(self):
        for name, html_out in self.pages.items():
            with self.subTest(page=name):
                self.assertRegex(html_out, r"<h1 [^>]*id=")
                self.assertTrue((self.out_dir / name).stat().st_size > 2000)

    def test_no_scripts_and_no_external_refs(self):
        for name, html_out in self.pages.items():
            with self.subTest(page=name):
                self.assertNotIn("<script", html_out)
                for url in re.findall(r'(?:href|src)="(http[^"]+)"', html_out):
                    self.fail(f"external reference {url!r} in {name}")

    def test_internal_links_resolve_to_files(self):
        for name, html_out in self.pages.items():
            for href in collect(html_out).links:
                if href.startswith("#") or href.startswith("http"):
                    continue
                target = href.split("#", 1)[0]
                with self.subTest(page=name, href=href):
                    self.assertTrue(
                        (self.out_dir / target).exists(), f"broken link {href}"
                    )

    def test_anchor_targets_exist(self):
        for name, html_out in self.pages.items():
            parsed = collect(html_out)
            local_ids = set(parsed.ids)
            for href in parsed.links:
                if "#" not in href:
                    continue
                target_page, frag = href.split("#", 1)
                if not target_page:
                    with self.subTest(page=name, frag=frag):
                        self.assertIn(frag, local_ids)
                elif target_page in self.pages:
                    with self.subTest(page=name, href=href):
                        target = collect(self.pages[target_page])
                        self.assertIn(frag, set(target.ids))

    def test_no_leftover_markdown(self):
        for name, html_out in self.pages.items():
            with self.subTest(page=name):
                self.assertNotIn("**", html_out)
                self.assertNotIn("](#", html_out)
                self.assertNotIn(".md)", html_out)

    def test_worksheet_is_interactive_and_printable(self):
        ws = self.pages["shift-cycle-planner.html"]
        self.assertGreaterEqual(ws.count('type="checkbox"'), 20)
        css = (self.out_dir / "styles.css").read_text(encoding="utf-8")
        self.assertIn("@media print", css)

    def test_glossary_covers_core_terms(self):
        gloss = self.pages["glossary.html"]
        for term in ("Anchor sleep", "Microsleep", "Caffeine half-life",
                     "Circadian rhythm", "Sleep debt", "Sleep window"):
            self.assertIn(term, gloss)

    def test_pager_navigation(self):
        first = self.pages["introduction.html"]
        last = self.pages["glossary.html"]
        self.assertIn("Home", first)
        self.assertIn("Sleep-window planning", first)
        self.assertIn("low-energy-recovery-day.html", last)

    def test_all_source_docs_have_titles(self):
        for md in sorted((ROOT / "docs").glob("*.md")):
            with self.subTest(doc=md.name):
                text = md.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("# "), f"{md.name} lacks an H1 title")
                lowered = text.lower()
                self.assertNotIn("todo", lowered)
                self.assertNotIn("fixme", lowered)
                self.assertNotIn("lorem ipsum", lowered)


class TestDeterminism(unittest.TestCase):
    def test_build_is_deterministic(self):
        with tempfile.TemporaryDirectory(prefix="nssg-det-") as tmp:
            out_a = Path(tmp) / "a"
            out_b = Path(tmp) / "b"
            subprocess.run([sys.executable, str(ROOT / "build.py"), "--out", str(out_a)],
                           check=True, capture_output=True)
            subprocess.run([sys.executable, str(ROOT / "build.py"), "--out", str(out_b)],
                           check=True, capture_output=True)
            for name in EXPECTED_PAGES:
                a = (out_a / name).read_bytes()
                b = (out_b / name).read_bytes()
                self.assertEqual(a, b, f"nondeterministic output: {name}")


if __name__ == "__main__":
    unittest.main()
