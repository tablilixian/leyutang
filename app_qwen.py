import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import torch
import gradio as gr
import soundfile as sf
import tempfile

from qwen_tts import Qwen3TTSModel

device = "mps" if torch.backends.mps.is_available() else "cpu"
print(f"Loading Qwen CustomVoice 0.6B on {device}...")

model = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
    device_map=device,
    dtype=torch.float32,
)

speakers = model.get_supported_speakers()
languages = model.get_supported_languages()
print(f"Speakers: {speakers}")
print(f"Languages: {languages}")

def generate(text, speaker, language, instruct):
    wavs, sr = model.generate_custom_voice(
        text=text,
        language=language,
        speaker=speaker,
        instruct=instruct if instruct else None,
    )
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    sf.write(tmp.name, wavs[0], sr)
    return tmp.name

with gr.Blocks(title="Qwen CustomVoice 0.6B 体验") as demo:
    gr.Markdown("# 🔊 Qwen CustomVoice 0.6B")
    gr.Markdown("通义千问 TTS · 9种预置音色 · 自然语言控制语气")

    with gr.Row():
        with gr.Column():
            text = gr.Textbox(
                label="文本",
                value="其实我真的有发现，我是一个特别善于观察别人情绪的人。",
                lines=3,
            )
            with gr.Row():
                speaker = gr.Dropdown(
                    choices=speakers,
                    value=speakers[0],
                    label="音色",
                )
                language = gr.Dropdown(
                    choices=languages,
                    value=languages[1] if len(languages) > 1 else languages[0],
                    label="语言",
                )
            instruct = gr.Textbox(
                label="语气指令（可选）",
                placeholder="用特别愤怒的语气说 / 用温柔平静的语气说 / 欢快地...",
                value="",
            )
            btn = gr.Button("🎤 生成语音", variant="primary")
        with gr.Column():
            out = gr.Audio(label="生成结果", type="filepath")

    btn.click(fn=generate, inputs=[text, speaker, language, instruct], outputs=out)

demo.launch(server_name="127.0.0.1", server_port=7868, css="footer {display:none !important}")
