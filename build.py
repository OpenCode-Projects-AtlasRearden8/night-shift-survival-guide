#!/usr/bin/env python3
"""Build the Night Shift Survival Guide static site from docs/*.md.

Dependency-free (Python standard library only) and fully local: the generated
site references no external assets, scripts, fonts, or network resources.

Usage:
    python3 build.py                  # build into ./site
    python3 build.py --out DIR        # build into DIR
    python3 build.py --clean          # wipe the output dir, then build
"""

import argparse
import html
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS_DIR = ROOT / "docs"
TEMPLATES_DIR = ROOT / "templates"
DEFAULT_OUT = ROOT / "site"

BOOK_TITLE = "Night Shift Survival Guide"
BOOK_TAGLINE = "A warm, plain-English field manual for nurses and other night workers."
COPYRIGHT = "2026 Asdale Dynamics, LLC"

PAGE_TEMPLATE = TEMPLATES_DIR / "page.html"
STYLESHEET = TEMPLATES_DIR / "styles.css"

CODE_TOKEN = "\x00"
TOKEN_RE = re.compile("\x00(\\d+)\x00")


class HeadingIds:
    def __init__(self):
        self._counts = {}

    def slug(self, text):
        base = slugify(text)
        n = self._counts.get(base, 0) + 1
        self._counts[base] = n
        return base if n == 1 else f"{base}-{n}"


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text.strip()).strip("-")
    return text or "section"


def escape_href(target):
    return html.escape(target, quote=True)


def render_inline(text):
    text = html.escape(text, quote=False)

    code_spans = []

    def keep_code(m):
        code_spans.append("<code>" + m.group(1) + "</code>")
        return f"{CODE_TOKEN}{len(code_spans) - 1}{CODE_TOKEN}"

    text = re.sub(r"`([^`]+)`", keep_code, text)

    def make_link(m):
        label, target = m.group(1), m.group(2)
        if "#" in target:
            head, _, frag = target.partition("#")
            if head.endswith(".md"):
                target = output_name(Path(head).stem) + "#" + frag
        elif target.endswith(".md"):
            target = output_name(Path(target).stem)
        return '<a href="' + escape_href(target) + '">' + label + "</a>"

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", make_link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*\s](?:[^*]*[^*\s])?)\*(?![\w*])", r"<em>\1</em>", text)
    text = TOKEN_RE.sub(lambda m: code_spans[int(m.group(1))], text)
    return text


UL_RE = re.compile(r"^(\s*)([-*+])\s+(.*)$")
OL_RE = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
TASK_RE = re.compile(r"^\[([ xX])\]\s*(.*)$")
SEP_CELL_RE = re.compile(r":?-{3,}:?")


def table_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def is_table_separator(line):
    cells = table_row(line)
    return bool(cells) and all(SEP_CELL_RE.fullmatch(c) for c in cells)


def alignment_of(cell):
    starts, ends = cell.startswith(":"), cell.endswith(":")
    if starts and ends:
        return "center"
    if ends:
        return "right"
    return "left"


def render_table(header_cells, aligns, rows):
    def cell(tag, content, align):
        style = f' style="text-align:{align}"' if align != "left" else ""
        return f"<{tag}{style}>{render_inline(content)}</{tag}>"

    head = "".join(cell("th", c, a) for c, a in zip(header_cells, aligns))
    body_rows = []
    for row in rows:
        padded = row + [""] * (len(header_cells) - len(row))
        body_rows.append(
            "<tr>" + "".join(cell("td", c, a) for c, a in zip(padded, aligns)) + "</tr>"
        )
    return (
        "<table><thead><tr>" + head + "</tr></thead><tbody>"
        + "".join(body_rows) + "</tbody></table>"
    )


def render_list_block(raw_items):
    def walk(start, indent, ordered):
        tag = "ol" if ordered else "ul"
        parts = [f"<{tag}>"]
        i = start
        while i < len(raw_items):
            ind, _, text, task = raw_items[i]
            if ind < indent:
                break
            j = i + 1
            while j < len(raw_items) and raw_items[j][0] > indent:
                j += 1
            child_html = ""
            if j > i + 1:
                child_ind, child_ordered = raw_items[i + 1][0], raw_items[i + 1][1]
                child_html, consumed = walk(i + 1, child_ind, child_ordered)
                i = consumed
            else:
                i = j
            if task is not None:
                check = " checked" if task else ""
                li_open = f'<li class="task"><input type="checkbox"{check}> {text}'
            else:
                li_open = f"<li>{text}"
            if child_html:
                parts.append(li_open + child_html + "</li>")
            else:
                parts.append(li_open + "</li>")
        parts.append(f"</{tag}>")
        return "".join(parts), i

    return walk(0, raw_items[0][0], raw_items[0][1])[0]


def render_markdown(src, ids=None):
    if ids is None:
        ids = HeadingIds()
    lines = src.replace("\r\n", "\n").split("\n")
    out = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(buf)) + "</code></pre>")
            continue

        heading = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if heading:
            level, text = len(heading.group(1)), heading.group(2)
            out.append(
                f'<h{level} id="{ids.slug(text)}">{render_inline(text)}</h{level}>'
            )
            i += 1
            continue

        if re.match(r"^-{3,}$", stripped) or re.match(r"^\*{3,}$", stripped):
            out.append("<hr>")
            i += 1
            continue

        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + render_markdown("\n".join(buf), ids) + "</blockquote>")
            continue

        if stripped.startswith("|") and i + 1 < n and is_table_separator(lines[i + 1]):
            header_cells = table_row(stripped)
            aligns = [alignment_of(c) for c in table_row(lines[i + 1])]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(table_row(lines[i]))
                i += 1
            out.append(render_table(header_cells, aligns, rows))
            continue

        ul_match = UL_RE.match(line)
        ol_match = OL_RE.match(line)
        if ul_match or ol_match:
            items = []
            while i < n:
                cur = lines[i]
                mul = UL_RE.match(cur)
                mol = OL_RE.match(cur)
                if not (mul or mol):
                    if (
                        items
                        and cur.strip()
                        and cur[:1] in (" ", "\t")
                        and not cur.lstrip().startswith((">", "|", "```", "#", "| "))
                    ):
                        items[-1][2] += " " + cur.strip()
                        i += 1
                        continue
                    break
                if mol:
                    indent, text, ordered = len(mol.group(1)), mol.group(3), True
                else:
                    indent, text, ordered = len(mul.group(1)), mul.group(3), False
                items.append([indent, ordered, text.strip(), None])
                i += 1
            prepared = []
            for indent, ordered, text, _ in items:
                task = None
                task_m = TASK_RE.match(text)
                if task_m:
                    task = task_m.group(1) in "xX"
                    text = task_m.group(2)
                prepared.append([indent, ordered, render_inline(text), task])
            out.append(render_list_block(prepared))
            continue

        buf = [line]
        i += 1
        while i < n:
            nxt = lines[i]
            s = nxt.strip()
            starts_block = (
                not s
                or s.startswith(("#", ">", "```", "|", "- ", "* ", "+ "))
                or re.match(r"^\d+[.)]\s", s)
                or re.match(r"^-{3,}$", s)
                or re.match(r"^\*{3,}$", s)
            )
            if starts_block:
                break
            buf.append(nxt)
            i += 1
        out.append("<p>" + render_inline(" ".join(b.strip() for b in buf)) + "</p>")

    return "\n".join(out)


def output_name(md_stem):
    return re.sub(r"^(\d+)-", "", md_stem) + ".html"


def plain_text(html_fragment):
    return html.unescape(re.sub(r"<[^>]+>", "", html_fragment))


def first_paragraph(md_html):
    m = re.search(r"<p>(.*?)</p>", md_html, re.DOTALL)
    if not m:
        return ""
    text = plain_text(m.group(1)).strip()
    if len(text) > 180:
        cut = text[:178]
        dot = cut.rfind(". ")
        if 60 < dot:
            text = cut[: dot + 1]
        else:
            text = cut.rstrip() + "…"
    return text


def read_text(path):
    return path.read_text(encoding="utf-8")


def render_page(template, *, page_title, description, nav, body, prev_html, next_html):
    full_title = BOOK_TITLE if page_title == BOOK_TITLE else f"{page_title} · {BOOK_TITLE}"
    return (
        template.replace("{{PAGE_TITLE}} · {{BOOK_TITLE}}", full_title)
        .replace("{{PAGE_TITLE}}", page_title)
        .replace("{{BOOK_TITLE}}", BOOK_TITLE)
        .replace("{{BOOK_TAGLINE}}", BOOK_TAGLINE)
        .replace("{{DESCRIPTION}}", escape_href(description))
        .replace("{{NAV}}", "<ul>" + nav + "</ul>")
        .replace("{{PREV}}", "        " + prev_html)
        .replace("{{NEXT}}", "        " + next_html)
        .replace("{{COPYRIGHT}}", COPYRIGHT)
        .replace("{{BODY}}", body)
    )


def build_index_body(chapters):
    cards = []
    for ch in chapters:
        cards.append(
            "<li><a href=\"{0}\"><span class=\"card-title\">{1}</span>"
            "<p class=\"card-blurb\">{2}</p></a></li>".format(
                ch["page"], ch["title"], escape_href(ch["desc"])
            )
        )
    return "\n".join(
        [
            '<section class="hero">',
            '<h1 id="top">' + BOOK_TITLE + "</h1>",
            f'<p class="lede">{BOOK_TAGLINE}</p>',
            "<p>Plain English, one small step at a time, never condescending. "
            "Built for nurses, paramedics, and everyone else who lives real life "
            "while the sun is on the wrong side of the sky.</p>",
            "</section>",
            '<div class="callout">',
            "<p><strong>First time here?</strong> Start with "
            '<a href="introduction.html">Start here</a>, then skim '
            '<a href="sleep-window-planning.html">sleep-window planning</a> and '
            'fill in the <a href="shift-cycle-planner.html">shift-cycle planner '
            "worksheet</a>. One small change per week beats a full overhaul you "
            "abandon by Friday.</p>",
            "</div>",
            "<h2>Chapters</h2>",
            '<ul class="cards">',
            "\n".join(cards),
            "</ul>",
            '<div class="callout">',
            "<p><strong>A note on scope:</strong> this is an education-only manual. "
            "It is not medical advice, not a protocol, and not a substitute for your "
            "own clinician, sleep clinic, or employee health department. You know "
            "your body; take what fits.</p>",
            "</div>",
            "<h2>About this site</h2>",
            "<ul>",
            "<li><strong>Local-first:</strong> every page works offline with no "
            "external fonts, scripts, trackers, or network calls.</li>",
            "<li><strong>Printable:</strong> any page — including the "
            '<a href="shift-cycle-planner.html">planner worksheet</a> — is '
            "print-tuned automatically.</li>",
            "<li><strong>Rebuildable:</strong> the whole site is generated from "
            "<code>docs/*.md</code> with <code>python3 build.py</code>.</li>",
            "</ul>",
        ]
    )


def build(out_dir=DEFAULT_OUT, clean=False):
    out_dir = Path(out_dir)
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    md_files = sorted(DOCS_DIR.glob("*.md"))
    if not md_files:
        raise RuntimeError("no markdown files found in docs/")

    template = read_text(PAGE_TEMPLATE)
    (out_dir / "styles.css").write_text(read_text(STYLESHEET), encoding="utf-8")

    ids = HeadingIds()
    chapters = []
    for path in md_files:
        md_html = render_markdown(read_text(path), ids)
        title_m = re.search(r"<h1[^>]*>(.*?)</h1>", md_html)
        title = plain_text(title_m.group(1)).strip() if title_m else path.stem
        chapters.append(
            {
                "page": output_name(path.stem),
                "title": title,
                "desc": first_paragraph(md_html),
                "body": md_html,
            }
        )

    nav_lines = [
        f'<li><a href="{ch["page"]}" class="navlink">{ch["title"]}</a></li>'
        for ch in chapters
    ]
    nav_plain = "\n".join(nav_lines)

    for idx, ch in enumerate(chapters):
        marked = f'href="{ch["page"]}" class="navlink"'
        nav = nav_plain.replace(marked, marked + " current")
        prev_html = (
            '<a class="prev" href="index.html">&larr; Home</a>'
            if idx == 0
            else '<a class="prev" href="{0}">&larr; {1}</a>'.format(
                chapters[idx - 1]["page"], chapters[idx - 1]["title"]
            )
        )
        if idx + 1 < len(chapters):
            nxt = chapters[idx + 1]
            next_html = '<a class="next" href="{0}">{1} &rarr;</a>'.format(
                nxt["page"], nxt["title"]
            )
        else:
            next_html = '<span class="gap"></span>'
        page_html = render_page(
            template,
            page_title=ch["title"],
            description=ch["desc"],
            nav=nav,
            body=ch["body"],
            prev_html=prev_html,
            next_html=next_html,
        )
        (out_dir / ch["page"]).write_text(page_html, encoding="utf-8")

    index_html = render_page(
        template,
        page_title=BOOK_TITLE,
        description=BOOK_TAGLINE,
        nav=nav_plain,
        body=build_index_body(chapters),
        prev_html='<span class="gap"></span>',
        next_html='<span class="gap"></span>',
    )
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")

    print(f"Built {len(chapters)} chapters + index -> {out_dir}")
    return out_dir


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the static site from docs/")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")
    parser.add_argument("--clean", action="store_true", help="wipe output dir before build")
    args = parser.parse_args(argv)
    if not DOCS_DIR.exists():
        print("error: docs/ not found", file=sys.stderr)
        return 1
    try:
        build(args.out, clean=args.clean)
    except Exception as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
