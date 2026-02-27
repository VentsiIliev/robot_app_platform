#!/usr/bin/env python3
"""
Serve the docs/ directory as a website in your browser.

Usage:
    python serve_docs.py              # opens http://localhost:7000
    python serve_docs.py --port 8080  # custom port
    python serve_docs.py --no-open   # don't auto-open browser

No external dependencies — stdlib only.
"""

import argparse
import html
import os
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote

# ── Config ────────────────────────────────────────────────────────────────────

ROOT     = Path(__file__).resolve().parent
DOCS_DIR = ROOT / "docs"
TITLE    = "Robot App Platform — Docs"


# ══════════════════════════════════════════════════════════════════════════════
# Markdown → HTML  (stdlib only, covers GFM subset used in this project)
# ══════════════════════════════════════════════════════════════════════════════

def md_to_html(text: str) -> str:
    """Convert a Markdown string to an HTML fragment."""

    lines   = text.splitlines()
    out     = []
    i       = 0

    def escape(s: str) -> str:
        return html.escape(s, quote=False)

    def inline(s: str) -> str:
        """Apply inline rules to a single line."""
        # fenced code spans  `...`
        s = re.sub(r'`([^`]+)`', lambda m: f'<code>{escape(m.group(1))}</code>', s)
        # **bold**
        s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
        # *italic* / _italic_
        s = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', s)
        s = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'<em>\1</em>', s)
        # ~~strikethrough~~
        s = re.sub(r'~~(.+?)~~', r'<del>\1</del>', s)
        # ![alt](url)
        s = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img alt="\1" src="\2">', s)
        # [text](url)
        s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
                   lambda m: f'<a href="{_fix_link(m.group(2))}">{m.group(1)}</a>', s)
        return s

    def _fix_link(href: str) -> str:
        """Convert relative .md links to routed doc links."""
        if href.startswith(("http://", "https://", "#", "/")):
            return href
        # relative path like ../engine/README.md  →  /doc/engine/README.md
        return href  # kept as-is; browser resolves relative to current URL

    def slug(text: str) -> str:
        return re.sub(r'[^a-z0-9-]', '-', text.lower().strip()).strip('-')

    n = len(lines)
    while i < n:
        line = lines[i]

        # ── Fenced code block  ```lang … ```
        m = re.match(r'^```(\w*)', line)
        if m:
            lang = m.group(1) or "text"
            i += 1
            code_lines = []
            while i < n and not lines[i].startswith("```"):
                code_lines.append(escape(lines[i]))
                i += 1
            i += 1  # skip closing ```
            out.append(f'<pre><code class="language-{escape(lang)}">'
                       + "\n".join(code_lines) + "</code></pre>")
            continue

        # ── Heading  # … ######
        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            text  = inline(escape(m.group(2)))
            id_   = slug(m.group(2))
            out.append(f'<h{level} id="{id_}">{text}</h{level}>')
            i += 1
            continue

        # ── Setext heading (underline with === or ---)
        if i + 1 < n:
            if re.match(r'^=+\s*$', lines[i + 1]):
                out.append(f'<h1>{inline(escape(line))}</h1>')
                i += 2
                continue
            if re.match(r'^-+\s*$', lines[i + 1]) and line.strip():
                out.append(f'<h2>{inline(escape(line))}</h2>')
                i += 2
                continue

        # ── Horizontal rule
        if re.match(r'^(-{3,}|_{3,}|\*{3,})\s*$', line):
            out.append("<hr>")
            i += 1
            continue

        # ── Blockquote
        if line.startswith("> "):
            bq_lines = []
            while i < n and lines[i].startswith("> "):
                bq_lines.append(lines[i][2:])
                i += 1
            inner = md_to_html("\n".join(bq_lines))
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        # ── Table  (GFM)
        if "|" in line and i + 1 < n and re.match(r'^\|?[\s\-:|]+\|', lines[i + 1]):
            header_cells = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2  # skip separator row
            rows = []
            while i < n and "|" in lines[i]:
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            ths = "".join(f"<th>{inline(escape(c))}</th>" for c in header_cells)
            body = ""
            for row in rows:
                tds = "".join(f"<td>{inline(escape(c))}</td>" for c in row)
                body += f"<tr>{tds}</tr>"
            out.append(f'<table><thead><tr>{ths}</tr></thead><tbody>{body}</tbody></table>')
            continue

        # ── Unordered list
        if re.match(r'^(\s*)([-*+])\s+', line):
            indent0 = len(line) - len(line.lstrip())
            items   = []
            while i < n and re.match(r'^\s*[-*+]\s+', lines[i]):
                items.append(inline(escape(re.sub(r'^\s*[-*+]\s+', '', lines[i]))))
                i += 1
            lis = "".join(f"<li>{it}</li>" for it in items)
            out.append(f"<ul>{lis}</ul>")
            continue

        # ── Ordered list
        if re.match(r'^\d+\.\s+', line):
            items = []
            while i < n and re.match(r'^\d+\.\s+', lines[i]):
                items.append(inline(escape(re.sub(r'^\d+\.\s+', '', lines[i]))))
                i += 1
            lis = "".join(f"<li>{it}</li>" for it in items)
            out.append(f"<ol>{lis}</ol>")
            continue

        # ── Blank line → paragraph break
        if not line.strip():
            out.append("<p></p>")
            i += 1
            continue

        # ── Paragraph / plain text
        para_lines = []
        while i < n and lines[i].strip() and not re.match(
                r'^(#{1,6}\s|```|>|\s*[-*+]\s|\d+\.\s|\|)', lines[i]):
            para_lines.append(lines[i])
            i += 1
        out.append("<p>" + inline(escape(" ".join(para_lines))) + "</p>")

    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════════
# Navigation tree builder
# ══════════════════════════════════════════════════════════════════════════════

def _label(path: Path) -> str:
    """Human-readable label for a path segment."""
    name = path.name
    # TEST_COVERAGE_REPORT.md → Test Coverage Report
    name = re.sub(r'[-_]', ' ', name)
    name = re.sub(r'\.md$', '', name, flags=re.IGNORECASE)
    return name.title()


def build_nav(base: Path, current_path: str) -> str:
    """Recursively build an HTML navigation tree for the sidebar."""

    def walk(directory: Path, depth: int) -> str:
        parts = []
        entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                # Only include dirs that contain .md files (recursively)
                md_count = sum(1 for _ in entry.rglob("*.md"))
                if md_count == 0:
                    continue
                sub = walk(entry, depth + 1)
                label = _label(entry)
                key   = entry.relative_to(base).as_posix()
                indent = "  " * depth
                parts.append(
                    f'{indent}<li class="nav-dir" data-key="{html.escape(key)}">'
                    f'<button class="nav-dir-label">{html.escape(label)}</button>'
                    f'<ul>{sub}</ul></li>'
                )
            elif entry.suffix.lower() in (".md",):
                rel   = "/" + entry.relative_to(base.parent).as_posix()
                label = _label(entry)
                active = "active" if rel == current_path else ""
                indent = "  " * depth
                parts.append(
                    f'{indent}<li class="nav-file {active}">'
                    f'<a href="{rel}">{html.escape(label)}</a></li>'
                )
        return "\n".join(parts)

    return f'<ul class="nav-root">{walk(base, 0)}</ul>'


# ══════════════════════════════════════════════════════════════════════════════
# HTML page template
# ══════════════════════════════════════════════════════════════════════════════

CSS = """
:root {
  --bg:        #0d1117;
  --bg-card:   #161b22;
  --bg-nav:    #0d1117;
  --border:    #30363d;
  --text:      #e6edf3;
  --text-dim:  #8b949e;
  --accent:    #58a6ff;
  --accent2:   #3fb950;
  --code-bg:   #1f2428;
  --nav-w:     260px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  display: flex;
  min-height: 100vh;
  font-size: 15px;
  line-height: 1.65;
}

/* ── Sidebar ── */
#sidebar {
  width: var(--nav-w);
  min-width: var(--nav-w);
  background: var(--bg-nav);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  position: sticky;
  top: 0;
  height: 100vh;
  padding: 16px 0 32px;
}

#sidebar h1 {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: .04em;
  text-transform: uppercase;
  color: var(--text-dim);
  padding: 0 16px 12px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 12px;
}

ul.nav-root, ul.nav-root ul { list-style: none; padding: 0; }

.nav-dir { padding: 0; }
.nav-dir-label {
  display: flex;
  align-items: center;
  gap: 5px;
  width: 100%;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: .04em;
  text-transform: uppercase;
  color: var(--text-dim);
  padding: 8px 16px 3px;
  text-align: left;
}
.nav-dir-label::before {
  content: '▾';
  font-size: 11px;
  line-height: 1;
  flex-shrink: 0;
  transition: transform .15s ease;
  display: inline-block;
}
.nav-dir-label:hover { color: var(--text); }
.nav-dir.collapsed > .nav-dir-label::before { transform: rotate(-90deg); }
.nav-dir.collapsed > ul { display: none; }

/* Indentation with vertical guide line for nested levels */
.nav-dir ul {
  padding-left: 0;
  margin-left: 20px;
  border-left: 1px solid var(--border);
}

.nav-file a {
  display: block;
  padding: 3px 10px;
  color: var(--text-dim);
  text-decoration: none;
  font-size: 13.5px;
  border-radius: 4px;
  margin: 1px 4px;
  transition: background .12s, color .12s;
}
.nav-file a:hover  { color: var(--text); background: #1c2128; }
.nav-file.active a { color: var(--accent); background: #1c2128; font-weight: 500; }

/* ── Main content ── */
#content {
  flex: 1;
  max-width: 900px;
  padding: 40px 48px 80px;
  overflow-x: hidden;
}

/* ── Typography ── */
h1, h2, h3, h4, h5, h6 {
  color: var(--text);
  font-weight: 600;
  margin: 1.6em 0 .5em;
  line-height: 1.25;
}
h1 { font-size: 2em;   border-bottom: 1px solid var(--border); padding-bottom: .3em; }
h2 { font-size: 1.5em; border-bottom: 1px solid var(--border); padding-bottom: .3em; }
h3 { font-size: 1.25em; }
h4 { font-size: 1em; }

p { margin: .75em 0; color: var(--text); }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
hr { border: none; border-top: 1px solid var(--border); margin: 1.5em 0; }

strong { font-weight: 600; }
del { color: var(--text-dim); }

/* ── Code ── */
code {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-size: .875em;
  background: var(--code-bg);
  padding: .15em .4em;
  border-radius: 4px;
  color: #f78166;
}
pre {
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  overflow-x: auto;
  margin: 1em 0;
}
pre code {
  color: #e6edf3;
  background: none;
  padding: 0;
  font-size: .875em;
}

/* ── Tables ── */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
  font-size: .9em;
}
thead { background: #1c2128; }
th, td {
  padding: 8px 12px;
  border: 1px solid var(--border);
  text-align: left;
  vertical-align: top;
}
th { font-weight: 600; color: var(--text); }
td code { font-size: .8em; }
tr:nth-child(even) { background: #0f1318; }

/* ── Lists ── */
ul, ol { padding-left: 1.5em; margin: .5em 0; }
li { margin: .25em 0; }

/* ── Blockquote ── */
blockquote {
  border-left: 3px solid var(--accent);
  margin: 1em 0;
  padding: .5em 1em;
  color: var(--text-dim);
  background: #1c2128;
  border-radius: 0 6px 6px 0;
}

/* ── Collapsible content sections ── */
.collapsible-h {
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 8px;
}
.collapsible-h::before {
  content: '▾';
  font-size: 0.65em;
  opacity: 0.45;
  flex-shrink: 0;
  transition: transform .15s ease;
  display: inline-block;
}
.collapsible-h.section-closed::before { transform: rotate(-90deg); }
.collapsible-h:hover::before { opacity: 0.9; }
.section-body.section-hidden { display: none; }

/* ── Breadcrumb ── */
#breadcrumb {
  font-size: 12px;
  color: var(--text-dim);
  margin-bottom: 20px;
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}
#breadcrumb a { color: var(--text-dim); }
#breadcrumb a:hover { color: var(--accent); }
#breadcrumb .sep { color: var(--border); }

/* ── Search box ── */
#search-wrap { padding: 8px 12px 12px; }
#search {
  width: 100%;
  background: #1c2128;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 13px;
  padding: 6px 10px;
  outline: none;
}
#search::placeholder { color: var(--text-dim); }
#search:focus { border-color: var(--accent); }

/* hide non-matching nav items */
.nav-file.search-hidden { display: none; }
"""

JS = """
(function() {
  // Default: everything collapsed. localStorage stores which dirs are OPEN.
  var STORAGE_KEY = 'nav-open-v1';

  function getOpen() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); }
    catch(e) { return []; }
  }
  function setOpen(keys) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(keys)); } catch(e) {}
  }

  // Collect ancestor dir keys of the active nav item — always kept open
  var ancestorKeys = [];
  var active = document.querySelector('.nav-file.active');
  if (active) {
    var el = active.parentElement;
    while (el) {
      if (el.classList && el.classList.contains('nav-dir') && el.dataset.key) {
        ancestorKeys.push(el.dataset.key);
      }
      el = el.parentElement;
    }
  }

  // Start all dirs collapsed, then open the ones in storage + ancestors
  var openKeys = getOpen();
  document.querySelectorAll('.nav-dir').forEach(function(dir) {
    var key = dir.dataset.key;
    var shouldOpen = openKeys.indexOf(key) !== -1 || ancestorKeys.indexOf(key) !== -1;
    if (!shouldOpen) {
      dir.classList.add('collapsed');
    }
  });

  // Toggle on label click
  document.querySelectorAll('.nav-dir-label').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var dir = btn.closest('.nav-dir');
      if (!dir) return;
      dir.classList.toggle('collapsed');
      var key = dir.dataset.key;
      var stored = getOpen();
      if (!dir.classList.contains('collapsed')) {
        // now open — add to stored
        if (stored.indexOf(key) === -1) stored.push(key);
      } else {
        // now closed — remove from stored
        stored = stored.filter(function(k) { return k !== key; });
      }
      setOpen(stored);
    });
  });

  // Live search filter
  var search = document.getElementById('search');
  if (search) {
    search.addEventListener('input', function() {
      var q = this.value.toLowerCase().trim();
      document.querySelectorAll('.nav-file').forEach(function(li) {
        if (!q || li.textContent.toLowerCase().includes(q)) {
          li.classList.remove('search-hidden');
        } else {
          li.classList.add('search-hidden');
        }
      });
      // While searching: expand all dirs with matches; on clear, restore state
      document.querySelectorAll('.nav-dir').forEach(function(dir) {
        var visible = dir.querySelectorAll('.nav-file:not(.search-hidden)').length;
        if (q) {
          dir.style.display = visible ? '' : 'none';
          if (visible) dir.classList.remove('collapsed');
        } else {
          dir.style.display = '';
          var stored = getOpen();
          var key = dir.dataset.key;
          var shouldOpen = stored.indexOf(key) !== -1 || ancestorKeys.indexOf(key) !== -1;
          dir.classList.toggle('collapsed', !shouldOpen);
        }
      });
    });
  }

  // Scroll active item into view
  if (active) active.scrollIntoView({ block: 'center', behavior: 'instant' });
})();

// ── Collapsible content sections (h2 level) ───────────────────────────────
// Default: all collapsed. localStorage stores which sections are OPEN.
(function() {
  var PAGE_KEY = 'sections-open:' + location.pathname;

  function getOpen() {
    try { return JSON.parse(localStorage.getItem(PAGE_KEY) || '[]'); }
    catch(e) { return []; }
  }
  function saveOpen(ids) {
    try { localStorage.setItem(PAGE_KEY, JSON.stringify(ids)); } catch(e) {}
  }

  var content = document.getElementById('content');
  if (!content) return;

  var headings = Array.from(content.querySelectorAll('h2'));
  var openIds = getOpen();

  headings.forEach(function(h) {
    // Collect all siblings after h until the next h2
    var body = [];
    var next = h.nextElementSibling;
    while (next && next.tagName !== 'H2') {
      body.push(next);
      next = next.nextElementSibling;
    }
    if (body.length === 0) return;

    // Wrap body in a div
    var wrapper = document.createElement('div');
    wrapper.className = 'section-body';
    h.parentNode.insertBefore(wrapper, body[0]);
    body.forEach(function(el) { wrapper.appendChild(el); });

    // Ensure heading has a stable id
    if (!h.id) h.id = 'section-' + h.textContent.trim().toLowerCase().replace(/\s+/g, '-');
    var id = h.id;

    h.classList.add('collapsible-h');

    // Default collapsed — only open if stored as open
    if (openIds.indexOf(id) === -1) {
      wrapper.classList.add('section-hidden');
      h.classList.add('section-closed');
    }

    // Toggle on click
    h.addEventListener('click', function() {
      var nowHidden = wrapper.classList.toggle('section-hidden');
      h.classList.toggle('section-closed', nowHidden);
      var stored = getOpen();
      if (!nowHidden) {
        if (stored.indexOf(id) === -1) stored.push(id);
      } else {
        stored = stored.filter(function(k) { return k !== id; });
      }
      saveOpen(stored);
    });
  });
})();
"""


def render_page(md_path: Path, current_url: str) -> bytes:
    """Render a .md file as a full HTML page."""
    raw  = md_path.read_text(encoding="utf-8")
    body = md_to_html(raw)
    nav  = build_nav(DOCS_DIR, current_url)

    # Breadcrumb: each segment of the URL path
    parts = [p for p in current_url.strip("/").split("/") if p]
    crumbs = [f'<a href="/">docs</a>']
    for idx, part in enumerate(parts):
        href  = "/" + "/".join(parts[: idx + 1])
        label = re.sub(r'[-_]', ' ', re.sub(r'\.md$', '', part, flags=re.IGNORECASE)).title()
        if idx == len(parts) - 1:
            crumbs.append(f'<span>{html.escape(label)}</span>')
        else:
            crumbs.append(f'<a href="{href}">{html.escape(label)}</a>')
    breadcrumb_html = " <span class='sep'>›</span> ".join(crumbs)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(md_path.stem.replace('_', ' ').title())} — {html.escape(TITLE)}</title>
  <style>{CSS}</style>
</head>
<body>
<nav id="sidebar">
  <h1>{html.escape(TITLE)}</h1>
  <div id="search-wrap">
    <input id="search" type="search" placeholder="Filter…" autocomplete="off">
  </div>
  {nav}
</nav>
<main id="content">
  <div id="breadcrumb">{breadcrumb_html}</div>
  {body}
</main>
<script>{JS}</script>
</body>
</html>"""
    return page.encode("utf-8")


def render_index() -> bytes:
    """Render the docs root index (list of top-level sections)."""
    sections = sorted(
        [d for d in DOCS_DIR.iterdir() if d.is_dir()],
        key=lambda p: p.name
    )
    cards = []
    for sec in sections:
        md_count = sum(1 for _ in sec.rglob("*.md"))
        label = _label(sec)
        # link to README.md if it exists, else first .md
        readme = sec / "README.md"
        if readme.exists():
            href = "/" + readme.relative_to(DOCS_DIR.parent).as_posix()
        else:
            first = next(sec.rglob("*.md"), None)
            href  = "/" + first.relative_to(DOCS_DIR.parent).as_posix() if first else "#"
        cards.append(f"""
      <a class="card" href="{href}">
        <div class="card-title">{html.escape(label)}</div>
        <div class="card-meta">{md_count} page{"s" if md_count != 1 else ""}</div>
      </a>""")

    nav = build_nav(DOCS_DIR, "/")
    extra_css = """
      .home-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:16px; margin-top:32px; }
      .card { display:block; background:#161b22; border:1px solid #30363d; border-radius:10px;
              padding:20px; text-decoration:none; transition:border-color .15s, transform .15s; }
      .card:hover { border-color:#58a6ff; transform:translateY(-2px); }
      .card-title { color:#e6edf3; font-weight:600; font-size:1.05em; margin-bottom:6px; }
      .card-meta  { color:#8b949e; font-size:.85em; }
    """
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(TITLE)}</title>
  <style>{CSS}{extra_css}</style>
</head>
<body>
<nav id="sidebar">
  <h1>{html.escape(TITLE)}</h1>
  <div id="search-wrap">
    <input id="search" type="search" placeholder="Filter…" autocomplete="off">
  </div>
  {nav}
</nav>
<main id="content">
  <h1>{html.escape(TITLE)}</h1>
  <p>Select a section below or use the sidebar to navigate.</p>
  <div class="home-grid">{"".join(cards)}</div>
</main>
<script>{JS}</script>
</body>
</html>"""
    return page.encode("utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# HTTP request handler
# ══════════════════════════════════════════════════════════════════════════════

class DocsHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # silence access log

    def do_GET(self):
        raw_path = unquote(self.path.split("?")[0])

        # Root → index
        if raw_path in ("/", ""):
            body = render_index()
            self._send(200, "text/html; charset=utf-8", body)
            return

        # Resolve to filesystem path (URL is relative to project root)
        fs_path = ROOT / raw_path.lstrip("/")

        # If it's a directory, redirect to its README.md
        if fs_path.is_dir():
            readme = fs_path / "README.md"
            if readme.exists():
                self._redirect("/" + readme.relative_to(ROOT).as_posix())
            else:
                first = next(fs_path.rglob("*.md"), None)
                if first:
                    self._redirect("/" + first.relative_to(ROOT).as_posix())
                else:
                    self._send(404, "text/plain; charset=utf-8", b"No markdown files found")
            return

        # Serve .md file as rendered HTML
        if fs_path.suffix.lower() in (".md",) and fs_path.is_file():
            body = render_page(fs_path, raw_path)
            self._send(200, "text/html; charset=utf-8", body)
            return

        # Fallback 404
        self._send(404, "text/plain; charset=utf-8",
                   f"Not found: {raw_path}".encode())

    def _send(self, code: int, ctype: str, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Serve docs/ as a local website")
    parser.add_argument("--port",    type=int, default=7000, help="Port to listen on (default: 7000)")
    parser.add_argument("--no-open", action="store_true",   help="Don't auto-open the browser")
    args = parser.parse_args()

    if not DOCS_DIR.exists():
        print(f"docs/ directory not found at {DOCS_DIR}")
        sys.exit(1)

    server = HTTPServer(("127.0.0.1", args.port), DocsHandler)
    url    = f"http://localhost:{args.port}"

    print(f"  Serving docs at  {url}")
    print(f"  Docs root        {DOCS_DIR}")
    print(f"  Press Ctrl+C to stop\n")

    if not args.no_open:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
