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
from .agentic_rag import agentic_rag
from .agentic_query import agentic_query
from .agentic_search import agentic_search
from .agentic_output import agentic_output

async def router_agent(user_input: str) -> AsyncGenerator[bytes, None]:
    """使用工具调用进行隐式路由。"""
    toolkit = Toolkit()
    toolkit.register_tool_function(agentic_rag)
    toolkit.register_tool_function(agentic_query)
    toolkit.register_tool_function(agentic_search)
    toolkit.register_tool_function(agentic_output)

    # 使用工具模块初始化路由智能体
    router = ReActAgent(
        name="Alice",
        sys_prompt=PROMPT['router_sys_prompt'],
        model=DashScopeChatModel(
            model_name=Config['MODEL'],
            api_key=Config['API_KEY'],
        ),
        formatter=DashScopeChatFormatter(),
        toolkit=toolkit,
    )
    
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