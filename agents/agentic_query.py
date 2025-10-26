import asyncio
import os
import sys
import json

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit, ToolResponse

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import Config
from prompt import PROMPT
from tools.parse_sleep_db import read_sleep_db
from tools.parse_heart_rate_db import read_heart_rate_db


# 模块级单例：避免每次调用都创建 Toolkit / ReActAgent
_query_toolkit = None
_query_agent = None

def _get_query_agent():
    global _query_toolkit, _query_agent
    if _query_agent is None:
        _query_toolkit = Toolkit()
        _query_toolkit.register_tool_function(read_sleep_db)
        _query_toolkit.register_tool_function(read_heart_rate_db)

        _query_agent = ReActAgent(
            name="Tom",
            sys_prompt=PROMPT['agentic_query_sys_prompt'],
            model=DashScopeChatModel(
                api_key=Config['API_KEY'],
                model_name=Config['MODEL'],
            ),
            formatter=DashScopeChatFormatter(),
            toolkit=_query_toolkit,
        )
    return _query_agent


async def agentic_query(demand: str) -> ToolResponse:
    """
    目前该智能体支持查询用户的睡眠数据、步数和心率数据，当需要时可以调用本工具函数。
    
    Args:
        demand (str):
            对用户数据库检索的需求。
    """
    # 使用模块级单例 agent（惰性初始化）
    query_agent = _get_query_agent()

    msg_res = await query_agent(Msg("user", demand, "user"))

    return ToolResponse(
        content=msg_res.get_content_blocks("text"),
    )