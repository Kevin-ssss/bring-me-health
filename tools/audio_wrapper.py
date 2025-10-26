# -*- coding: utf-8 -*-
"""本地封装：将 DashScope 文本转音频并保存到项目的 output 目录。

此函数与 agentscope 中的 `dashscope_text_to_audio` 功能等价，但在生成
音频后会把二进制音频写入到 `output_dir`（默认为 `Config['OUTPUT_DIR']`），
并在返回的 ToolResponse 中加入一个 `TextBlock`，包含已保存的文件绝对路径。
"""
import base64
import os
from typing import Literal, Any

import shortuuid

from agentscope.message import AudioBlock, TextBlock
from agentscope.tool._response import ToolResponse

import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import Config


def dashscope_text_to_audio_local(
    text: str,
    api_key: str,
    model: str = "sambert-zhichu-v1",
    sample_rate: int = 48000,
    output_dir: str | None = None,
) -> ToolResponse:
    """将文本合成为音频，并把生成的音频保存到 output_dir。

    返回值为 ToolResponse，内容包含原始的 AudioBlock（base64）以及一个
    TextBlock，用来告知已保存文件的绝对路径。
    """
    try:
        import dashscope

        dashscope.api_key = api_key

        res = dashscope.audio.tts.SpeechSynthesizer.call(
            model=model,
            text=text,
            sample_rate=sample_rate,
            format="wav",
        )

        audio_data = res.get_audio_data()

        if audio_data is not None:
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")

            # ensure output dir
            out_dir = output_dir or Config.get('OUTPUT_DIR') or os.path.abspath('./output')
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception:
                out_dir = os.path.abspath('.')

            filename = f"tts_{shortuuid.uuid()}.wav"
            file_path = os.path.join(out_dir, filename)
            try:
                with open(file_path, 'wb') as f:
                    f.write(audio_data)
            except Exception:
                # If saving fails, still return base64 data
                file_path = None

            blocks = []
            blocks.append(
                AudioBlock(
                    type="audio",
                    source={
                        "type": "base64",
                        "media_type": "audio/wav",
                        "data": audio_base64,
                    },
                )
            )

            if file_path:
                blocks.append(
                    TextBlock(
                        type="text",
                        text=f"<saved_audio>{os.path.abspath(file_path)}</saved_audio>",
                    )
                )

            return ToolResponse(content=blocks)
        else:
            return ToolResponse([
                TextBlock(type="text", text="Error: Failed to generate audio"),
            ])
    except Exception as e:
        return ToolResponse([
            TextBlock(type="text", text=f"Failed to generate audio: {str(e)}"),
        ])
