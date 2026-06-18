#!/usr/bin/env python3
"""
patch_html_audio.py — 为乐育堂语录所有文章页面注入音频播放器

功能:
  1. 扫描所有 解读_*.html 文章页面，注入音频播放器 HTML/CSS/JS
  2. 更新 index.html，在每个文章链接前显示音频状态徽标 (🔊 或 ⏳)
  3. 幂等安全 — 重复运行不会重复注入

用法:
  python3 patch_html_audio.py

音频文件约定 (放入 audio/ 目录):
  audio/{文章文件名不含.html}_yuansheng.wav   原文朗读
  audio/{文章文件名不含.html}_yishu.wav       译文朗读
  audio/{文章文件名不含.html}_jiedu.wav       现代解读
  audio/{文章文件名不含.html}_drama.wav       广播剧

生成的文件:
  audio-player.css      — 播放器样式
  audio-player.js       — 播放器逻辑
"""

import re
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
AUDIO_DIR = ROOT / "audio"

CSS_LINK = '<link rel="stylesheet" href="audio-player.css">'
JS_SCRIPT = '<script src="audio-player.js"></script>'

SECTIONS = [
    ("yuansheng", "原文朗读", "_yuansheng.mp3"),

    ("yishu", "译文朗读", "_yishu.mp3"),

    ("jiedu", "现代解读", "_jiedu.mp3"),

    ("drama", "广播剧", "_drama.mp3"),
]

BADGE_CSS = """
.audio-badge { display:inline-block; font-size:11px; margin-right:4px; vertical-align:middle; line-height:1; }
.audio-badge.ready { color:var(--accent,#8b4513); }
.audio-badge.pending { color:#ccc; }
"""


def get_audio_sources(base_name):
    """检查某个文章有哪些音频文件可用，返回 sources 列表"""
    if not AUDIO_DIR.is_dir():
        return []
    sources = []
    for key, label, suffix in SECTIONS:
        ap = AUDIO_DIR / f"{base_name}{suffix}"
        if ap.exists():
            sources.append({
                "key": key,
                "label": label,
                "src": f"audio/{base_name}{suffix}",
            })
    return sources


def patch_article_html(filepath):
    """在单篇文章页面中注入或更新播放器"""
    print(f"  {filepath.name}")
    html = filepath.read_text("utf-8")

    base_name = filepath.stem
    sources = get_audio_sources(base_name)
    config_json = json.dumps(sources, ensure_ascii=False)

    # 替换已有的 config，或注入新的
    config_pattern = re.compile(
        r'<script>window\.__AUDIO_SOURCES__\s*=\s*[^<]+</script>'
    )
    new_config = f'<script>window.__AUDIO_SOURCES__ = {config_json};</script>'

    if config_pattern.search(html):
        html = config_pattern.sub(new_config, html)
        config_updated = True
    else:
        html = html.replace("</body>", f"  {new_config}\n</body>")
        config_updated = False

    # 注入 CSS link (仅首次)
    if CSS_LINK not in html:
        html = html.replace("</head>", f"  {CSS_LINK}\n</head>")

    # 注入 JS script (仅首次)
    if JS_SCRIPT not in html:
        html = html.replace("</body>", f"  {JS_SCRIPT}\n</body>")

    filepath.write_text(html, "utf-8")

    count = len(sources)
    if config_updated:
        print(f"     ✓ 配置已更新 ({count} 个音频片段)" if count else "     ✓ 配置已更新 (暂无音频)")
    else:
        print(f"     ✓ 已注入 ({count} 个音频片段)" if count else "     ✓ 已注入 (暂无音频，播放器隐藏)")


def patch_index_html():
    """更新首页，添加/刷新音频状态徽标"""
    fp = ROOT / "index.html"
    print(f"  index.html")
    html = fp.read_text("utf-8")

    # 注入 CSS link (仅首次)
    if CSS_LINK not in html:
        html = html.replace("</head>", f"  {CSS_LINK}\n</head>")

    # 注入徽标 CSS (仅首次)
    if "audio-badge" not in html:
        html = html.replace("</style>", BADGE_CSS.rstrip() + "\n</style>")

    # 给每个 toc-item 链接加上/更新徽标
    def badge_replacer(m):
        href = m.group(1)
        inner = m.group(2)
        # 如果 inner 里已有 audio-badge 则移除，避免嵌套
        inner_clean = re.sub(r'<span class="audio-badge[^>]*>.*?</span>\s*', '', inner)
        base = href.rsplit(".", 1)[0]
        sources = get_audio_sources(base)
        if sources:
            badge = '<span class="audio-badge ready">🔊</span>'
        else:
            badge = '<span class="audio-badge pending">⏳</span>'
        return f'<a href="{href}" class="toc-item">{badge}{inner_clean}</a>'

    toc_pat = re.compile(
        r'<a href="(解读_[^"]+\.html)" class="toc-item">(.*?)</a>',
        re.DOTALL,
    )
    html = toc_pat.sub(badge_replacer, html)

    # 注入 JS 脚本 (仅首次)
    if JS_SCRIPT not in html:
        html = html.replace("</body>", f"  {JS_SCRIPT}\n</body>")

    fp.write_text(html, "utf-8")
    print("     ✓ 徽标已更新")


def main():
    print("=" * 52)
    print("  乐育堂语录 · 音频播放器注入工具")
    print("=" * 52)
    print()

    # 1) 更新首页
    print("[1/2] 更新 index.html ...")
    patch_index_html()
    print()

    # 2) 更新所有文章页面
    articles = sorted(ROOT.glob("解读_*.html"))
    print(f"[2/2] 处理 {len(articles)} 篇文章 ...")
    for fpath in articles:
        patch_article_html(fpath)

    print()
    print("=" * 52)
    print("  全部完成！")
    print()
    print("  生成的资源文件:")
    print("    audio-player.css  播放器样式")
    print("    audio-player.js   播放器逻辑")
    print()
    print(f"  已处理 {len(articles)} 个文章页面")
    print("  已更新 index.html")
    print()
    print("  将音频文件放入 audio/ 目录后重新运行本脚本")
    print("  即可自动更新音频状态。")
    print("=" * 52)


if __name__ == "__main__":
    main()
