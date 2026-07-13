#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert 乐育堂语录/丹道次第实操手册.md to a styled HTML page matching the project reader."""
import re, html, os

SRC = "乐育堂语录/丹道次第实操手册.md"
OUT = "丹道次第实操手册.html"

CSS = """
:root {
  --bg: #f8f5f0;
  --card-bg: #fff;
  --text: #333;
  --text-light: #666;
  --accent: #8b4513;
  --accent-light: #a0522d;
  --border: #e0d5c8;
}
* { margin:0; padding:0; box-sizing:border-box; }
body {
  font-family: "Noto Serif SC", "Source Han Serif SC", serif;
  background: var(--bg); color: var(--text); line-height: 1.85; font-size: 17px;
}
.container { max-width: 860px; margin: 0 auto; padding: 20px; }
header { text-align:center; padding: 40px 20px 26px; border-bottom: 2px solid var(--accent); margin-bottom: 26px; }
header h1 { font-size: 2.05em; color: var(--accent); margin-bottom: 10px; font-weight: 600; }
header p { color: var(--text-light); font-size: 0.95em; }
.card { background:#fff; border-radius:12px; padding: 28px 30px; margin-bottom: 22px; box-shadow:0 2px 8px rgba(0,0,0,0.06); border:1px solid var(--border); }
.card > h2 { font-size: 1.35em; color: var(--accent); margin: 4px 0 16px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }
.card h3 { font-size: 1.08em; color: var(--accent-light); margin: 20px 0 8px; }
.card p { margin-bottom: 12px; text-align: justify; }
.card blockquote { border-left: 4px solid var(--accent); padding: 4px 18px; margin: 14px 0; color: var(--text-light); font-style: italic; background:#faf7f2; border-radius:0 6px 6px 0; }
.card hr { border:none; border-top:1px solid var(--border); margin: 22px 0; }
.card ul { margin: 8px 0 14px 1.4em; }
.card li { margin-bottom: 7px; }
.card strong { color: var(--accent); }
.card table { width:100%; border-collapse: collapse; margin: 14px 0 18px; font-size: 0.92em; }
.card th, .card td { border: 1px solid var(--border); padding: 9px 11px; text-align: left; vertical-align: top; }
.card th { background: #f3ece1; color: var(--accent); font-weight: 600; }
.toc { background:#fff; border-radius:12px; padding: 22px 26px; margin-bottom: 22px; box-shadow:0 2px 8px rgba(0,0,0,0.06); border:1px solid var(--border); }
.toc h2 { font-size:1.25em; color: var(--accent); margin-bottom:12px; }
.toc ol { margin-left: 1.4em; }
.toc li { margin-bottom: 8px; }
.toc a, .backlink { color: var(--accent); text-decoration: none; }
.toc a:hover, .backlink:hover { text-decoration: underline; }
.step-badge { display:inline-block; background: var(--accent); color:#fff; font-size:0.68em; padding: 2px 9px; border-radius: 10px; margin-left: 8px; vertical-align: middle; }
.backbar { text-align:center; margin: 6px 0 22px; font-size:0.9em; }
.footer { text-align:center; padding: 34px 20px; color: var(--text-light); font-size:0.85em; border-top:1px solid var(--border); margin-top: 30px; }
@media (max-width: 600px){ body{font-size:15px;} header h1{font-size:1.55em;} .card{padding:18px;} .card table{font-size:0.82em;} }
"""

CN = "一二三四五六七八九十"

def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    return t

def parse_table(lines):
    rows = [ [c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines ]
    head, body = rows[0], rows[2:]
    out = ['<table><thead><tr>'] + ['<th>%s</th>' % inline(c) for c in head] + ['</tr></thead><tbody>']
    for r in body:
        out += ['<tr>'] + ['<td>%s</td>' % inline(c) for c in r] + ['</tr>']
    return ''.join(out) + '</tbody></table>'

def convert(md):
    lines = md.split("\n")
    i, n = 0, len(lines)
    parts, toc = [], []
    seen_title = False
    sec_count = 0
    in_card = False

    def close_card():
        nonlocal in_card
        if in_card:
            parts.append("</div>\n"); in_card = False

    def open_card(title):
        nonlocal sec_count, in_card
        close_card()
        sec_count += 1
        anchor = "sec%d" % sec_count
        m = re.match(r"第([%s]+)步" % CN, title)
        if m:
            num = CN.index(m.group(1)) + 1
            toc.append((anchor, title))
            parts.append('<div class="card" id="%s"><h2>%s<span class="step-badge">第%d步</span></h2>\n' % (anchor, inline(title), num))
        else:
            toc.append((anchor, title))
            parts.append('<div class="card" id="%s"><h2>%s</h2>\n' % (anchor, inline(title)))
        in_card = True

    while i < n:
        ln = lines[i]
        if ln.strip() == "":
            i += 1; continue
        if ln.startswith("# "):
            if not seen_title:
                seen_title = True; i += 1; continue
            open_card(ln[2:].strip()); i += 1; continue
        if ln.startswith("## "):
            open_card(ln[3:].strip()); i += 1; continue
        if ln.startswith("### "):
            parts.append('<h3>%s</h3>\n' % inline(ln[4:].strip())); i += 1; continue
        if ln.startswith("> "):
            bq = []
            while i < n and lines[i].startswith("> "):
                bq.append(lines[i][2:]); i += 1
            parts.append('<blockquote>%s</blockquote>\n' % inline(" ".join(bq))); continue
        if ln.strip() == "---":
            parts.append('<hr>\n'); i += 1; continue
        if ln.strip().startswith("|") and i+1 < n and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i+1]):
            j = i; tbl = []
            while j < n and lines[j].strip().startswith("|"):
                tbl.append(lines[j]); j += 1
            parts.append(parse_table(tbl) if in_card else '<div class="card">'+parse_table(tbl)+'</div>\n')
            i = j; continue
        if re.match(r"^\s*-\s+", ln):
            items = []
            while i < n and re.match(r"^\s*-\s+", lines[i]):
                items.append('<li>%s</li>' % inline(re.sub(r"^\s*-\s+", "", lines[i]))); i += 1
            parts.append('<ul>%s</ul>\n' % "".join(items)); continue
        para = []
        while (i < n and lines[i].strip() != "" and not lines[i].startswith(("#","-",">"))
               and lines[i].strip() != "---" and not lines[i].strip().startswith("|")):
            para.append(lines[i]); i += 1
        if para:
            parts.append('<p>%s</p>\n' % inline(" ".join(p.strip() for p in para)))
        else:
            i += 1

    close_card()
    toc_html = '<div class="toc"><h2>目录</h2><ol>' + "".join(
        '<li><a href="#%s">%s</a></li>' % (a, html.escape(t)) for a, t in toc) + '</ol></div>\n'
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>乐育堂语录 · 丹道次第实操手册</title>
<style>%s</style>
</head>
<body>
<div class="container">
<header>
<h1>丹道次第实操手册</h1>
<p>（清）黄元吉《乐育堂语录》原文提炼 · 修炼步骤与验证</p>
</header>
<div class="backbar"><a class="backlink" href="index.html">← 返回《乐育堂语录》总目录</a></div>
%s
%s
<div class="footer">
<p>《乐育堂语录》丹道次第实操手册</p>
<p>依据清·黄元吉 著 · 九州出版社 2013 年版原文整理</p>
</div>
</div>
</body>
</html>
""" % (CSS, toc_html, "".join(parts))

if __name__ == "__main__":
    md = open(SRC, encoding="utf-8").read()
    out = convert(md)
    open(OUT, "w", encoding="utf-8").write(out)
    print("wrote", OUT, len(out), "bytes; cards:", out.count('class="card"'), "; toc:", out.count('href="#sec'))
