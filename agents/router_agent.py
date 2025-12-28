import asyncio
import os
import sys
import json
from typing import AsyncGenerator

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit, execute_python_code, execute_shell_command, dashscope_text_to_audio

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import Config
from prompt import PROMPT

# 导入所有工具函数
from tools.build_sleep_vdbs import get_sleep_knowledge
from tools.build_heart_rate_vdbs import get_heart_rate_knowledge
from tools.parse_sleep_db import read_sleep_db
from tools.parse_heart_rate_db import read_heart_rate_db
from tools.web_search import web_search
from tools.pubmed_search import pubmed_search
from tools.exec_wrapper import execute_python_code_local
from tools.audio_wrapper import dashscope_text_to_audio_local


# 模块级单例：避免每次请求都新建 Router Agent
_router_toolkit = None
_router_agent = None

def _get_router_agent():
    global _router_toolkit, _router_agent
    if _router_agent is None:
        _router_toolkit = Toolkit()
        
        # 注册所有工具函数
        # 睡眠和心率知识库查询工具
        _router_toolkit.register_tool_function(get_sleep_knowledge)
        _router_toolkit.register_tool_function(get_heart_rate_knowledge)
        
        # 用户健康数据查询工具
        _router_toolkit.register_tool_function(read_sleep_db)
        _router_toolkit.register_tool_function(read_heart_rate_db)
        
        # 网络搜索工具
        _router_toolkit.register_tool_function(web_search)
        _router_toolkit.register_tool_function(pubmed_search)
        
        # 代码执行和音频生成工具
        _router_toolkit.register_tool_function(
            execute_python_code_local, preset_kwargs={'output_dir': Config['OUTPUT_DIR']}
        )
        _router_toolkit.register_tool_function(
            dashscope_text_to_audio_local, preset_kwargs={'api_key': Config['API_KEY'], 'output_dir': Config['OUTPUT_DIR']}
        )
        
        _router_agent = ReActAgent(
            name="Alice",
            sys_prompt=PROMPT['router_sys_prompt'],
            model=DashScopeChatModel(
                model_name=Config['MODEL'],
                api_key=Config['API_KEY'],
            ),
            formatter=DashScopeChatFormatter(),
            toolkit=_router_toolkit,
        )
    return _router_agent


async def router_agent(user_input: str) -> AsyncGenerator[bytes, None]:
    """使用工具调用进行隐式路由。"""
    router = _get_router_agent()
    msg_user = Msg("user", user_input, "user")

    # 路由查询
    msg_res = await router(msg_user)

    results: str = msg_res.get_content_blocks("text")[0]['text']

    chunk_size = 3
    for i in range(0, len(results), chunk_size):
        yield results[i:i+chunk_size].encode('utf-8')
        await asyncio.sleep(0)      # 让出控制权，防止阻塞事件循环
        await asyncio.sleep(0.1)    # 可调打字间隔
        
    return