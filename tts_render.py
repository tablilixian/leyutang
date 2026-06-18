"""
将广播剧脚本渲染为 MP3 音频（供 GitHub Pages 部署）。

用法:
    python3 tts_render.py <脚本文件.md>

脚本格式:
    - 顶部有【角色与声音映射】表格, 格式: 角色名 = tts引擎:voice_id
    - 每行 [角色名] 台词的格式
    - (括号内) 的提示将被剥离但保留为音效标记
    - [旁白] 行作为叙述旁白

引擎支持:
    - edge-tts: 本地 Docker (localhost:5050)
    - chattts: 本地 Gradio (seed-based)
    - f5tts: 本地进程 (voice-cloning)

输出格式: MP3 (节省约 10x 空间，适合 GitHub Pages)
"""

import re, os, sys, json, tempfile
import subprocess
from pathlib import Path

# ===== 配置 =====
EDGE_TTS_API = "http://127.0.0.1:5050/v1/audio/speech"
EDGE_TTS_AUTH = "Bearer your_api_key_here"
OUTPUT_DIR = Path("output_audio")
OUTPUT_DIR.mkdir(exist_ok=True)

# 各角色语速调整（Edge-TTS 原生语速差异补偿）
# 旁白(XiaoxiaoNeural)默认偏慢，保持1.0
# 其他角色偏快，调低speed值来放慢
VOICE_SPEED = {
    "zh-CN-XiaoxiaoNeural": 1.0,            # 旁白·女声（保持现状）
    "zh-CN-YunxiNeural": 0.85,              # 老周·男声（偏快→放慢）
    "zh-CN-XiaoyiNeural": 0.85,             # 妻子·年轻女声（偏快→放慢）
    "zh-CN-YunyangNeural": 0.80,            # 同事·青年男声（最快→放慢最多）
    "zh-CN-YunjianNeural": 0.90,            # 老人·老年男声（略放慢）
    "zh-CN-liaoning-XiaobeiNeural": 0.80,   # 儿童·童声（偏快→放慢）
    "zh-CN-YunxiaNeural": 0.85,             # 其他男声
}

# ===== 解析脚本 =====

def parse_script(filepath: Path):
    """解析广播剧脚本"""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    voice_map = {}   # 角色 -> (引擎, voice_id)
    segments = []    # [(角色, 台词), ...]

    parsing_map = False
    parsing_script = False

    for line in lines:
        line = line.rstrip()

        # 检测映射表
        if "角色与声音映射" in line or "角色映射" in line:
            parsing_map = True
            continue
        if parsing_map:
            m = re.match(r'^-\s+(\S+)\s*=\s*([^:]+):([^\s（(]+)', line)
            if m:
                role, engine, voice = m.groups()
                voice_map[role] = (engine, voice)
                continue
            # 映射表结束: 空行、标题、或脚本开始
            if line.strip() == "" or line.startswith("#") or "脚本" in line:
                if "脚本" in line:
                    parsing_script = True
                    parsing_map = False
                else:
                    parsing_map = False
                continue

        # 检测脚本段
        if "脚本" in line and not parsing_script:
            parsing_script = True
            continue

        if not parsing_script:
            continue
        if line.startswith("---") or line.strip() == "":
            continue

        # 解析 [角色] 台词
        m = re.match(r'^\s*\[([^\]]+)\]\s*(.*?)$', line)
        if m:
            role = m.group(1).strip()
            text = m.group(2).strip()
            # 剥离括号内的舞台提示，保留内容标记
            text_clean = re.sub(r'[（(][^）)]*[）)]', '', text).strip()
            # 剥离引号
            text_clean = text_clean.strip('"').strip('"')
            if text_clean:
                segments.append((role, text_clean))

    return voice_map, segments


# ===== TTS 引擎 =====

def tts_edge(voice: str, text: str, output_path: str):
    """使用 Edge-TTS API 生成"""
    # 文本太长时分段
    max_chars = 500
    if len(text) > max_chars:
        segments = []
        while text:
            seg = text[:max_chars]
            text = text[max_chars:]
            segments.append(seg)
    else:
        segments = [text]

    # 获取该角色的语速设置，默认1.0
    speed = VOICE_SPEED.get(voice, 1.0)

    temp_files = []
    for i, seg in enumerate(segments):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        payload = {
            "model": "tts-1",
            "input": seg,
            "voice": voice,
            "response_format": "mp3",
        }
        if speed != 1.0:
            payload["speed"] = speed
        resp = subprocess.run([
            "curl", "-s", "-X", "POST", EDGE_TTS_API,
            "-H", "Content-Type: application/json",
            "-H", f"Authorization: {EDGE_TTS_AUTH}",
            "-d", json.dumps(payload),
            "-o", tmp,
        ], capture_output=True)

        if resp.returncode != 0:
            print(f"    Edge-TTS 请求失败: {resp.stderr.decode()}")
            return None
        if os.path.getsize(tmp) == 0:
            print(f"    Edge-TTS 返回空文件，重试...")
            resp = subprocess.run([
                "curl", "-s", "-X", "POST", EDGE_TTS_API,
                "-H", "Content-Type: application/json",
                "-H", f"Authorization: {EDGE_TTS_AUTH}",
                "-d", json.dumps(payload),
                "-o", tmp,
            ], capture_output=True)
            if resp.returncode != 0 or os.path.getsize(tmp) == 0:
                print(f"    ❌ 重试失败")
                return None
        temp_files.append(tmp)

    # 合并多段（MP3 直接拼接）
    if len(temp_files) == 1:
        os.rename(temp_files[0], output_path)
        return output_path
    else:
        subprocess.run([
            "ffmpeg", "-y", "-i", f"concat:{'|'.join(temp_files)}",
            "-c", "copy", output_path
        ], capture_output=True)
        for f in temp_files:
            os.unlink(f)
        return output_path


def render_script(script_file: str, output_name: str = None):
    """渲染整个广播剧脚本"""
    filepath = Path(script_file)
    voice_map, segments = parse_script(filepath)

    if not voice_map:
        print("❌ 未找到角色-声音映射表")
        return
    if not segments:
        print("❌ 未找到台词")
        return

    print(f"📋 角色映射: {voice_map}")
    print(f"📝 台词段落: {len(segments)} 条")

    # 生成每段音频
    audio_files = []
    for i, (role, text) in enumerate(segments):
        if role not in voice_map:
            print(f"  ⚠️  跳过未知角色 [{role}]: {text[:20]}...")
            continue

        engine, voice = voice_map[role]
        out_file = OUTPUT_DIR / f"seg_{i:04d}_{role}.mp3"

        if engine == "edge-tts":
            print(f"  [{i+1}/{len(segments)}] {role}: {text[:30]}...", end=" ", flush=True)
            result = tts_edge(voice, text, str(out_file))
        else:
            print(f"  ⚠️  不支持的引擎: {engine}")
            continue

        if result:
            size_kb = os.path.getsize(str(out_file)) / 1024
            print(f"  ✅ {size_kb:.0f}KB")
            audio_files.append(str(out_file))
        else:
            print(f"  ❌ 失败")

    # 合并全部音频（用 ffmpeg concat）
    if audio_files:
        combined = OUTPUT_DIR / (output_name or f"{filepath.stem}_combined.mp3")
        filelist_path = OUTPUT_DIR / "_filelist.txt"
        # 过滤掉 0 字节的文件，用绝对路径
        valid_files = [af for af in audio_files if os.path.getsize(af) > 0]
        with open(filelist_path, "w") as f:
            for af in valid_files:
                f.write(f"file '{os.path.abspath(af)}'\n")

        result = subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(filelist_path),
            "-c:a", "libmp3lame", "-q:a", "2", str(combined)
        ], capture_output=True)

        filelist_path.unlink()
        if result.returncode == 0 and os.path.exists(str(combined)) and os.path.getsize(str(combined)) > 0:
            print(f"\n🎉 合成完成: {combined} ({os.path.getsize(str(combined))/1024:.0f}KB)")
            return combined
        else:
            print(f"\n❌ 合并失败: {result.stderr.decode()[:200]}")
            return None
    else:
        print("❌ 没有成功生成的音频")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 tts_render.py <脚本.md>")
        sys.exit(1)

    render_script(sys.argv[1])
