#!/usr/bin/env python3
"""Assemble the report.

Concatenates report/sections/*.md, substitutes <!-- TABLE:name --> placeholders
with tables generated from data/, writes report/report.md, and renders a
standalone HTML version into docs/.

    python3 scripts/build_site.py            # markdown + html
    python3 scripts/build_site.py --figures  # regenerate all 24 figures first
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import markdown

import tables
from theme import ROOT

SECTIONS = ROOT / "report" / "sections"
REPORT_MD = ROOT / "report" / "report.md"
FIGURES = ROOT / "report" / "figures"
DOCS = ROOT / "docs"

PLACEHOLDER = re.compile(r"<!--\s*TABLE:([a-z0-9_]+)\s*-->")

CSS = """
:root {
  --ink: #16202a; --muted: #5b6b7a; --line: #dde4ea; --panel: #f6f8fa;
  --accent: #1a73e8; --nvidia: #76b900; --warn: #c5221f; --bg: #ffffff;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.68 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
#layout { display: flex; align-items: flex-start; max-width: 1600px; margin: 0 auto; }
nav {
  position: sticky; top: 0; flex: 0 0 296px; height: 100vh; overflow-y: auto;
  padding: 30px 20px 60px 26px; border-right: 1px solid var(--line);
  background: var(--panel); font-size: 13.5px;
}
nav .brand { font-weight: 700; font-size: 15px; letter-spacing: -0.01em; margin-bottom: 4px; }
nav .sub { color: var(--muted); font-size: 12px; margin-bottom: 20px; }
nav a { display: block; color: var(--muted); text-decoration: none; padding: 4px 8px;
        border-radius: 6px; border-left: 2px solid transparent; }
nav a:hover { color: var(--accent); background: #fff; }
nav a.h2 { color: var(--ink); font-weight: 600; margin-top: 10px; }
nav a.h3 { padding-left: 20px; font-size: 12.8px; }
main { flex: 1 1 auto; min-width: 0; padding: 46px 56px 120px; max-width: 1180px; }
h1 { font-size: 33px; line-height: 1.22; letter-spacing: -0.022em; margin: 0 0 10px; }
h2 { font-size: 25px; letter-spacing: -0.018em; margin: 56px 0 14px; padding-top: 14px;
     border-top: 1px solid var(--line); }
h3 { font-size: 18.5px; margin: 34px 0 10px; }
h4 { font-size: 15.5px; margin: 24px 0 8px; color: var(--muted); text-transform: uppercase;
     letter-spacing: 0.06em; }
p { margin: 0 0 15px; }
strong { font-weight: 650; }
a { color: var(--accent); }
hr { display: none; }
code { background: var(--panel); border: 1px solid var(--line); border-radius: 5px;
       padding: 1px 5px; font-size: 13.2px;
       font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; }
pre { background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
      padding: 16px 18px; overflow-x: auto; font-size: 13px; line-height: 1.55; }
pre code { background: none; border: none; padding: 0; }
blockquote { margin: 0 0 16px; padding: 2px 18px; border-left: 3px solid var(--accent);
             color: var(--muted); }
ul, ol { margin: 0 0 16px; padding-left: 22px; }
li { margin-bottom: 6px; }
img { display: block; width: 100%; height: auto; margin: 26px 0 8px;
      border: 1px solid var(--line); border-radius: 10px; background: #fff; }
.figure-caption { color: var(--muted); font-size: 12.6px; margin: -2px 0 30px; }
table { border-collapse: collapse; width: 100%; margin: 18px 0 26px; font-size: 13.4px;
        display: block; overflow-x: auto; }
th, td { border-bottom: 1px solid var(--line); padding: 8px 11px; text-align: left;
         vertical-align: top; white-space: nowrap; }
th { background: var(--panel); font-weight: 650; font-size: 12.6px; position: sticky; top: 0; }
tbody tr:hover { background: #fafcfe; }
td:first-child, th:first-child { white-space: normal; min-width: 150px; }
.badge { display: inline-block; padding: 1px 7px; border-radius: 20px; font-size: 11.5px;
         font-weight: 600; }
footer { margin-top: 70px; padding-top: 20px; border-top: 1px solid var(--line);
         color: var(--muted); font-size: 13px; }
@media (max-width: 1080px) {
  nav { display: none; }
  main { padding: 28px 20px 80px; }
  h1 { font-size: 27px; }
}
"""

HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GPUs and TPUs for LLM Training — A Technical and Commercial Field Guide</title>
<meta name="description" content="How GPUs and TPUs work, what every current AI accelerator's specifications are, what they cost, and how they compare.">
<style>{css}</style>
</head>
<body>
<div id="layout">
<nav>
  <div class="brand">GPUs &amp; TPUs for LLM Training</div>
  <div class="sub">Technical and commercial field guide · 20 August 2026</div>
  {toc}
</nav>
<main>
{body}
<footer>
Generated from <code>data/*.csv</code> by <code>scripts/build_site.py</code>.
Figures are produced by <code>scripts/fig_diagrams.py</code> and <code>scripts/fig_data.py</code>.
Every quantitative claim carries a confidence label; see the appendix for conflicts and unknowns.
</footer>
</main>
</div>
</body>
</html>
"""


def load_sections() -> str:
    parts = []
    for path in sorted(SECTIONS.glob("*.md")):
        parts.append(path.read_text().rstrip() + "\n")
    return "\n".join(parts)


def substitute_tables(text: str) -> str:
    def repl(match: re.Match) -> str:
        name = match.group(1)
        return tables.render(name)

    text, n = PLACEHOLDER.subn(repl, text)
    print(f"  substituted {n} generated tables")
    return text


def slugify(title: str) -> str:
    s = title.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"[\s_]+", "-", s).strip("-")


def build_toc(md_text: str) -> str:
    out = []
    for line in md_text.splitlines():
        m = re.match(r"^(#{2,3})\s+(.*)$", line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        out.append(f'<a class="h{level}" href="#{slugify(title)}">{title}</a>')
    return "\n  ".join(out)


def add_heading_ids(html: str) -> str:
    def repl(match: re.Match) -> str:
        tag, attrs, text = match.group(1), match.group(2), match.group(3)
        plain = re.sub(r"<[^>]+>", "", text)
        return f'<{tag} id="{slugify(plain)}"{attrs}>{text}</{tag}>'

    return re.sub(r"<(h[23])([^>]*)>(.*?)</\1>", repl, html, flags=re.S)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--figures", action="store_true", help="regenerate all figures first")
    args = ap.parse_args()

    if args.figures:
        import fig_data
        import fig_diagrams
        from theme import apply_style

        apply_style()
        print("Regenerating figures:")
        for fn in fig_diagrams.DIAGRAMS + fig_data.FIGURES:
            fn()

    print("Building report:")
    md_text = substitute_tables(load_sections())
    REPORT_MD.write_text(md_text)
    words = len(md_text.split())
    print(f"  wrote {REPORT_MD.relative_to(ROOT)}  ({words:,} words)")

    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "attr_list", "md_in_html", "sane_lists"],
    )
    html_body = add_heading_ids(html_body)
    # Images live under figures/ relative to the html file too.
    DOCS.mkdir(exist_ok=True)
    docs_figures = DOCS / "figures"
    if docs_figures.exists():
        shutil.rmtree(docs_figures)
    shutil.copytree(FIGURES, docs_figures)

    (DOCS / "index.html").write_text(
        HTML.format(css=CSS, toc=build_toc(md_text), body=html_body)
    )
    n_figs = len(list(docs_figures.glob("*.png")))
    print(f"  wrote {(DOCS / 'index.html').relative_to(ROOT)}  ({n_figs} figures copied)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
