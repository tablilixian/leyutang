import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import torch
import ChatTTS
import gradio as gr
import soundfile as sf
import numpy as np
import tempfile

device = "mps" if torch.backends.mps.is_available() else "cpu"

chat = ChatTTS.Chat()
chat.load(source="huggingface", compile=False if device == "mps" else True)


def generate(text1, seed1, text2, seed2, text3, seed3):
    texts = [t for t in [text1, text2, text3] if t.strip()]
    seeds = [int(s) for s, t in zip([seed1, seed2, seed3], [text1, text2, text3]) if t.strip()]

    audios = []
    for text, seed in zip(texts, seeds):
        torch.manual_seed(seed)
        wav = chat.infer([text], use_decoder=True)[0]
        audios.append(wav)

    audio = np.concatenate(audios) if len(audios) > 1 else audios[0]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    sf.write(tmp.name, audio, 24000)
    return tmp.name


with gr.Blocks(title="乐育堂语录 · 广播剧制作", css="footer {display:none !important}") as demo:
    gr.Markdown("# 🎙️ 乐育堂语录 · 广播剧制作")
    gr.Markdown("用 ChatTTS 分角色朗读。改 Seed 换音色，越不同角色声音差异越大。")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### 角色 1")
            t1 = gr.Textbox(label="文本", value="老周今年四十七岁，在一家广告公司做创意总监。")
            s1 = gr.Number(label="Seed (音色)", value=42, minimum=0, maximum=9999, step=1)
        with gr.Column():
            gr.Markdown("### 角色 2")
            t2 = gr.Textbox(label="文本", value="我都四十七了。")
            s2 = gr.Number(label="Seed (音色)", value=222, minimum=0, maximum=9999, step=1)
        with gr.Column():
            gr.Markdown("### 角色 3")
            t3 = gr.Textbox(label="文本", value="张三丰六十岁才出门访道呢。")
            s3 = gr.Number(label="Seed (音色)", value=555, minimum=0, maximum=9999, step=1)

    btn = gr.Button("🎬 生成广播剧")
    audio_out = gr.Audio(label="结果", type="filepath")

    btn.click(fn=generate, inputs=[t1, s1, t2, s2, t3, s3], outputs=audio_out)

demo.launch(server_name="127.0.0.1", server_port=7865)
