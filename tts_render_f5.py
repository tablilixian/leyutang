import os, re, sys, json, tempfile, time
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import torch
device = "mps" if torch.backends.mps.is_available() else "cpu"

from f5_tts.api import F5TTS
f5_model = F5TTS(device=device)
print(f"F5-TTS model loaded on {device}")

EDGE_TTS_API = "http://127.0.0.1:5050/v1/audio/speech"
EDGE_TTS_AUTH = "Bearer your_api_key_here"
OUTPUT_DIR = Path("output_audio")
OUTPUT_DIR.mkdir(exist_ok=True)

# 各角色语速补偿（Edge-TTS 原生语速差异）
VOICE_SPEED = {
    "zh-CN-XiaoxiaoNeural": 1.0,            # 旁白·女声（保持现状）
    "zh-CN-YunxiNeural": 0.85,              # 老周·男声
    "zh-CN-XiaoyiNeural": 0.85,             # 妻子·年轻女声
    "zh-CN-YunyangNeural": 0.80,            # 同事·青年男声
    "zh-CN-YunjianNeural": 0.90,            # 老人·老年男声
    "zh-CN-liaoning-XiaobeiNeural": 0.80,   # 儿童·童声
    "zh-CN-YunxiaNeural": 0.85,
}

REF_TEXT = "话说天下大势，分久必合，合久必分。周末七国分争，并入于秦。及秦灭之后，楚汉分争，又并入于汉。汉朝自高祖斩白蛇而起义，一统天下，后来光武中兴，传至献帝，遂分为三国。"

def find_ref_file(filename, script_dir):
    paths = [
        Path(filename),
        script_dir / filename,
        Path.cwd() / filename,
        Path(__file__).parent / filename,
    ]
    for p in paths:
        if p.exists():
            return str(p.resolve())
    return None

def tts_f5(ref_file: str, text: str, output_path: str):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f5_model.infer(
            ref_file=ref_file,
            ref_text=REF_TEXT,
            gen_text=text,
            file_wave=f.name,
        )
        data, sr = sf.read(f.name)
        sf.write(output_path, data, sr)
        os.unlink(f.name)
    return output_path

def tts_edge(voice: str, text: str, output_path: str):
    max_chars = 500
    if len(text) > max_chars:
        segs = []
        while text:
            segs.append(text[:max_chars])
            text = text[max_chars:]
    else:
        segs = [text]
    temp_files = []
    for seg in segs:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        speed = VOICE_SPEED.get(voice, 1.0)
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
            print(f"    Edge-TTS request failed: {resp.stderr.decode()}")
            return None
        temp_files.append(tmp)
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

def tts_chattts(seed: int, text: str, output_path: str):
    import ChatTTS
    chat = ChatTTS.Chat()
    chat.load(source="huggingface", compile=False if device == "mps" else True)
    torch.manual_seed(seed)
    wav = chat.infer([text], use_decoder=True)[0]
    sf.write(output_path, wav, 24000)
    return output_path

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
            text_clean = text_clean.strip('"').strip('"')
            if text_clean:
                segments.append((role, text_clean))
    return voice_map, segments

def render_script(script_file: str, output_name: str = None):
    filepath = Path(script_file)
    script_dir = filepath.parent
    voice_map, segments = parse_script(filepath)

    if not voice_map:
        print("No role-voice mapping found")
        return
    if not segments:
        print("No dialogue found")
        return

    print(f"Role mapping: {voice_map}")
    print(f"Dialogues: {len(segments)} lines\n")

    audio_files = []
    total_start = time.time()
    f5_count = 0

    for i, (role, text) in enumerate(segments):
        if role not in voice_map:
            print(f"  [{i+1}/{len(segments)}] Skip unknown role [{role}]: {text[:20]}...")
            continue

        engine, voice = voice_map[role]
        out_file = OUTPUT_DIR / f"seg_{i:04d}_{role}.wav"

        print(f"  [{i+1}/{len(segments)}] {role}: \"{text[:30]}...\"", end=" ", flush=True)
        seg_start = time.time()

        try:
            if engine == "f5tts":
                ref_path = find_ref_file(voice, script_dir)
                if ref_path is None:
                    print(f"  REF FILE NOT FOUND: {voice}")
                    continue
                tts_f5(ref_path, text, str(out_file))
                elapsed = time.time() - seg_start
                dur = len(sf.read(str(out_file))[0]) / 24000
                print(f"  {dur:.1f}s ({elapsed:.0f}s infer)")
                audio_files.append(str(out_file))
                f5_count += 1

            elif engine == "edge-tts":
                result = tts_edge(voice, text, str(out_file))
                elapsed = time.time() - seg_start
                if result:
                    dur = os.path.getsize(str(out_file)) / (24000 * 2)
                    print(f"  {dur:.1f}s ({elapsed:.1f}s)")
                    audio_files.append(str(out_file))
                else:
                    print(" FAILED")

            elif engine == "chattts":
                result = tts_chattts(int(voice), text, str(out_file))
                elapsed = time.time() - seg_start
                dur = len(sf.read(str(out_file))[0]) / 24000
                print(f"  {dur:.1f}s ({elapsed:.1f}s)")
                audio_files.append(str(out_file))

            else:
                print(f"  Unknown engine: {engine}")

        except Exception as e:
            print(f"  ERROR: {e}")

    total_elapsed = time.time() - total_start

    if not audio_files:
        print("\nNo audio generated")
        return

    sample_rate = 24000
    silence = np.zeros(int(0.5 * sample_rate))
    combined = []
    durations = []
    for af in audio_files:
        data, sr = sf.read(af)
        if sr != sample_rate:
            import librosa
            data = librosa.resample(data, orig_sr=sr, target_sr=sample_rate)
        combined.append(data)
        combined.append(silence)
        durations.append(len(data) / sample_rate)

    combined = np.concatenate(combined)
    name = output_name or f"{filepath.stem}_combined.wav"
    out_path = OUTPUT_DIR / name
    sf.write(str(out_path), combined, sample_rate)

    total_dur = len(combined) / sample_rate
    size_mb = os.path.getsize(str(out_path)) / (1024 * 1024)

    print(f"\n{'='*50}")
    print(f"Rendering complete!")
    print(f"  Output: {out_path}")
    print(f"  Total duration: {total_dur:.1f}s")
    print(f"  File size: {size_mb:.1f} MB")
    print(f"  Segments: {len(audio_files)} total ({f5_count} F5-TTS)")
    print(f"  Total processing time: {total_elapsed:.0f}s ({total_elapsed/60:.1f}min)")
    print(f"  Average per segment: {total_elapsed/len(audio_files):.0f}s")
    print(f"{'='*50}")

    if f5_count > 0:
        for i, af in enumerate(audio_files):
            role_name = Path(af).stem.split("_", 2)[-1]
            print(f"  {role_name}: {durations[i]:.1f}s")

    return str(out_path)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 tts_render_f5.py <script.md>")
        sys.exit(1)
    render_script(sys.argv[1])
