import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import torch
import gradio as gr
import tempfile
import soundfile as sf

device = "mps" if torch.backends.mps.is_available() else "cpu"

from f5_tts.api import F5TTS
model = F5TTS(device=device)

def generate(ref_audio, ref_text, gen_text):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        model.infer(
            ref_file=ref_audio,
            ref_text=ref_text,
            gen_text=gen_text,
            output=f.name,
        )
        return f.name

with gr.Blocks(title="F5-TTS 语音克隆演示") as demo:
    gr.Markdown("# 🎙️ F5-TTS 语音克隆")
    gr.Markdown("上传一段参考音频，克隆该声音后朗读任意文本。声音越清晰、越干净效果越好。")

    with gr.Row():
        with gr.Column():
            ref_audio = gr.Audio(label="参考音频（3-30秒）", type="filepath")
            ref_text = gr.Textbox(label="参考音频对应的文本", value="老周今年四十七岁，在一家广告公司做创意总监。")
            gen_text = gr.Textbox(label="要生成的目标文本", value="我都四十七了。", lines=3)
            btn = gr.Button("🔊 生成")
        with gr.Column():
            out_audio = gr.Audio(label="生成结果", type="filepath")

    btn.click(generate, inputs=[ref_audio, ref_text, gen_text], outputs=out_audio)

demo.launch(server_name="127.0.0.1", server_port=7867)
