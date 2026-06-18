#!/usr/bin/env python3
"""
batch_render.py — 批量将广播剧脚本渲染为 MP3，输出到 audio/ 目录

用法:
    python3 batch_render.py [--resume] [--start N] [--end N] [--max-chars 500]

命名映射:
    - 卷四: 解读_卷四第一条.md → audio/解读_卷四第1条_drama.mp3
    - 卷五: 解读_卷五第十条.md → audio/解读_卷五第10条_drama.mp3
    - 其他卷: 按源文件名直出
    - 卷一跳过中文数字的重复文件
"""

import re, os, sys, json, tempfile, time, argparse
import subprocess
from pathlib import Path

EDGE_TTS_API = "http://127.0.0.1:5050/v1/audio/speech"
EDGE_TTS_AUTH = "Bearer your_api_key_here"

DRAMA_DIR = Path("乐育堂语录_广播剧")
AUDIO_DIR = Path("audio")
TMP_DIR = Path("output_audio")

VOICE_SPEED = {
    "zh-CN-XiaoxiaoNeural": 1.0,
    "zh-CN-YunxiNeural": 0.85,
    "zh-CN-XiaoyiNeural": 0.85,
    "zh-CN-YunyangNeural": 0.80,
    "zh-CN-YunjianNeural": 0.90,
    "zh-CN-liaoning-XiaobeiNeural": 0.80,
    "zh-CN-YunxiaNeural": 0.85,
}

CN_NUM_MAP = {
    '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
}


def cn_to_arabic(cn: str) -> int:
    cn = cn.strip()
    if cn.isdigit():
        return int(cn)
    if '十' not in cn:
        return CN_NUM_MAP.get(cn, 0)
    parts = cn.split('十')
    left = CN_NUM_MAP.get(parts[0], 1) if parts[0] else 1
    right = CN_NUM_MAP.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
    return left * 10 + right


def drama_to_audio_path(drama_file: str) -> str:
    stem = Path(drama_file).stem
    vol_match = re.match(r'(解读_卷[一二三四五])第([\u4e00-\u9fff0-9]+)条', stem)
    if vol_match:
        vol = vol_match.group(1)
        num_str = vol_match.group(2)
        article_num = cn_to_arabic(num_str)
        return f"{vol}第{article_num}条_drama.mp3"
    return f"{stem}_drama.mp3"


def parse_script(filepath: Path):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    voice_map = {}
    segments = []
    parsing_map = False
    parsing_script = False
    for line in lines:
        line = line.rstrip()
        if "角色与声音映射" in line or "角色映射" in line:
            parsing_map = True
            continue
        if parsing_map:
            m = re.match(r'^-\s+(\S+)\s*=\s*([^:]+):([^\s（(]+)', line)
            if m:
                role, engine, voice = m.groups()
                voice_map[role] = (engine, voice)
                continue
            if line.strip() == "" or line.startswith("#") or "脚本" in line:
                if "脚本" in line:
                    parsing_script = True
                    parsing_map = False
                else:
                    parsing_map = False
                continue
        if "脚本" in line and not parsing_script:
            parsing_script = True
            continue
        if not parsing_script:
            continue
        if line.startswith("---") or line.strip() == "":
            continue
        m = re.match(r'^\s*\[([^\]]+)\]\s*(.*?)$', line)
        if m:
            role = m.group(1).strip()
            text = m.group(2).strip()
            text_clean = re.sub(r'[（(][^）)]*[）)]', '', text).strip()
            text_clean = text_clean.strip('"').strip('\u201c').strip('\u201d')
            if text_clean:
                segments.append((role, text_clean))
    return voice_map, segments


def tts_edge(voice: str, text: str, output_path: str, max_chars: int = 500):
    if len(text) > max_chars:
        segs = []
        while text:
            segs.append(text[:max_chars])
            text = text[max_chars:]
    else:
        segs = [text]

    speed = VOICE_SPEED.get(voice, 1.0)
    temp_files = []
    for seg in segs:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        payload = {
            "model": "tts-1",
            "input": seg,
            "voice": voice,
            "response_format": "mp3",
        }
        if speed != 1.0:
            payload["speed"] = speed
        for attempt in range(3):
            resp = subprocess.run([
                "curl", "-s", "-X", "POST", EDGE_TTS_API,
                "-H", "Content-Type: application/json",
                "-H", f"Authorization: {EDGE_TTS_AUTH}",
                "-d", json.dumps(payload),
                "-o", tmp,
            ], capture_output=True)
            if resp.returncode == 0 and os.path.getsize(tmp) > 200:
                break
            time.sleep(2)
        else:
            for f in temp_files:
                os.unlink(f)
            return None
        temp_files.append(tmp)

    if len(temp_files) == 1:
        os.rename(temp_files[0], output_path)
        return output_path
    else:
        concat_input = "|".join(temp_files)
        result = subprocess.run([
            "ffmpeg", "-y", "-i", f"concat:{concat_input}",
            "-c", "copy", output_path
        ], capture_output=True)
        for f in temp_files:
            os.unlink(f)
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path
        return None


def render_one(drama_file: str, max_chars: int = 500):
    filepath = Path(drama_file)
    if not filepath.exists():
        print(f"  ❌ 文件不存在: {drama_file}")
        return False

    audio_name = drama_to_audio_path(drama_file)
    audio_path = AUDIO_DIR / audio_name

    if audio_path.exists():
        print(f"  ⏭️ 已存在，跳过: {audio_name}")
        return True

    voice_map, segments = parse_script(filepath)
    if not voice_map:
        print(f"  ❌ 未找到角色映射: {drama_file}")
        return False
    if not segments:
        print(f"  ❌ 未找到台词: {drama_file}")
        return False

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    seg_files = []
    total = len(segments)
    for i, (role, text) in enumerate(segments):
        if role not in voice_map:
            voice_map[role] = ("edge-tts", "zh-CN-YunxiNeural")
            print(f"\r  [{i+1}/{total}] ⚠️ 未映射角色 [{role}]，使用默认音色", end="", flush=True)

        engine, voice = voice_map[role]
        if engine != "edge-tts":
            print(f"\r  [{i+1}/{total}] ⚠️ 不支持的引擎: {engine}", end="")
            continue

        out_file = str(TMP_DIR / f"seg_{i:04d}.mp3")
        result = tts_edge(voice, text, out_file, max_chars)
        if result:
            size_kb = os.path.getsize(out_file) / 1024
            print(f"\r  [{i+1}/{total}] {role}... ✅ {size_kb:.0f}KB", end="", flush=True)
            seg_files.append(out_file)
        else:
            print(f"\r  [{i+1}/{total}] {role}... ❌", end="", flush=True)

    print()

    if not seg_files:
        print(f"  ❌ 没有成功生成的片段")
        return False

    filelist = TMP_DIR / "_filelist.txt"
    valid_files = [af for af in seg_files if os.path.getsize(af) > 0]
    with open(filelist, "w") as f:
        for af in valid_files:
            f.write(f"file '{os.path.abspath(af)}'\n")

    result = subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(filelist),
        "-c:a", "libmp3lame", "-q:a", "2", str(audio_path)
    ], capture_output=True)

    filelist.unlink()
    for f in seg_files:
        os.unlink(f)

    if result.returncode == 0 and audio_path.exists() and audio_path.stat().st_size > 0:
        print(f"  ✅ 合成完成: {audio_name} ({audio_path.stat().st_size/1024:.0f}KB)")
        return True
    else:
        print(f"  ❌ 合成失败")
        return False


def is_chinese_numeral_dup(filepath: Path) -> bool:
    """Detect if this is a Chinese-numeral duplicate for vol 1 (skip it)"""
    stem = filepath.stem
    m = re.match(r'解读_卷一第([\u4e00-\u9fff]+)条', stem)
    if not m:
        return False
    num_str = m.group(1)
    if num_str.isdigit():
        return False
    if 'for_tts' in stem:
        return True
    return True


def main():
    parser = argparse.ArgumentParser(description="批量渲染广播剧音频")
    parser.add_argument("--resume", action="store_true", help="跳过已存在的文件")
    parser.add_argument("--start", type=int, default=None, help="起始序号")
    parser.add_argument("--end", type=int, default=None, help="结束序号")
    parser.add_argument("--max-chars", type=int, default=500, help="每段最大字符数")
    parser.add_argument("--list", action="store_true", help="仅列出待处理文件")
    args = parser.parse_args()

    print("=" * 52)
    print("  乐育堂语录 · 批量音频渲染")
    print("=" * 52)
    print()
    print(f"  Edge-TTS API: {EDGE_TTS_API}")
    print(f"  Max chars/seg: {args.max_chars}")
    print()

    files = sorted(DRAMA_DIR.glob("解读_*.md"))
    to_render = []
    for f in files:
        if is_chinese_numeral_dup(f):
            continue
        if 'for_tts' in f.stem:
            continue
        audio_name = drama_to_audio_path(str(f))
        if args.resume and (AUDIO_DIR / audio_name).exists():
            continue
        to_render.append(f)

    print(f"  广播剧脚本总数: {len(files)}")
    print(f"  需渲染: {len(to_render)}")
    print()

    if args.list:
        print("待渲染文件列表:")
        for f in to_render:
            audio_name = drama_to_audio_path(str(f))
            status = "✅" if (AUDIO_DIR / audio_name).exists() else "⏳"
            print(f"  {status} {f.name} → {audio_name}")
        return

    if args.start is not None or args.end is not None:
        s = (args.start or 1) - 1
        e = args.end or len(to_render)
        to_render = to_render[s:e]

    if not to_render:
        print("所有音频已生成完毕！")
        return

    print(f"开始渲染 {len(to_render)} 个脚本...")
    print()

    stats = {"ok": 0, "fail": 0}
    start_time = time.time()

    for i, f in enumerate(to_render):
        audio_name = drama_to_audio_path(str(f))
        print(f"\n[{i+1}/{len(to_render)}] {f.name}")
        print(f"  → {audio_name}")
        ok = render_one(str(f), args.max_chars)
        if ok:
            stats["ok"] += 1
        else:
            stats["fail"] += 1
        eta = (time.time() - start_time) / (i + 1) * (len(to_render) - i - 1) / 60
        print(f"  进度: {i+1}/{len(to_render)} | 成功: {stats['ok']} | 失败: {stats['fail']} | 预计剩余: {eta:.0f}min")

    elapsed = (time.time() - start_time) / 60
    print()
    print("=" * 52)
    print(f"  渲染完成！")
    print(f"  成功: {stats['ok']} | 失败: {stats['fail']}")
    print(f"  耗时: {elapsed:.1f} 分钟")
    print("=" * 52)


if __name__ == "__main__":
    main()
