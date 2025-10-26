import asyncio
import os
import sys

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit, ToolResponse, execute_python_code, execute_shell_command, dashscope_text_to_audio

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import Config
from prompt import PROMPT


# 模块级单例：避免每次调用都创建 Toolkit / ReActAgent
_output_toolkit = None
_output_agent = None

def _get_output_agent():
    global _output_toolkit, _output_agent
    if _output_agent is None:
        _output_toolkit = Toolkit()
        _output_toolkit.register_tool_function(execute_python_code)
        _output_toolkit.register_tool_function(execute_shell_command)
        # 注册时使用预置参数
        _output_toolkit.register_tool_function(dashscope_text_to_audio, preset_kwargs={'api_key': Config['API_KEY']})

        _output_agent = ReActAgent(
            name="Watson",
            sys_prompt=PROMPT['agentic_output_sys_prompt'],
            model=DashScopeChatModel(
                api_key=Config['API_KEY'],
                model_name=Config['MODEL'],
            ),
            formatter=DashScopeChatFormatter(),
            toolkit=_output_toolkit,
        )
    return _output_agent


async def agentic_output(demand: str) -> ToolResponse:
    """
    将多模态内容生成模块与 ReActAgent 集成，实现对编写和运行Python代码，或将文本转换为音频的任务处理。
    本工具智能体只接受两种需求(demands)类型：
        1. 编写和运行作图的Python代码，保存图像文件到目标文件夹，返回图像文件地址。
        2. 将文本转换为音频，保存音频文件到目标文件夹，返回音频文件地址。
    
    Args:
        demand (str):
            对编写和运行Python代码，执行Shell命令，或将文本转换为音频的需求。
    """
    # 使用模块级单例 agent（惰性初始化）
    rag_agent = _get_output_agent()

    msg_res = await rag_agent(Msg("user", demand, "user"))

    return ToolResponse(
        content=msg_res.get_content_blocks("text"),
    )
    
