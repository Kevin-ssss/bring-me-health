import asyncio
import os
import sys

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

async def agentic_query(demand: str) -> ToolResponse:
    """
    调用 ReActAgent 实现对用户数据库的查询。
    目前该智能体支持查询用户的睡眠数据、步数和心率数据，当需要时可以调用本工具函数。
    
    Args:
        demand (str):
            对用户数据库检索的需求。
    """
    # 创建工具箱
    toolkit = Toolkit()
    toolkit.register_tool_function(read_sleep_db)
    toolkit.register_tool_function(read_heart_rate_db)

    # 使用 DashScope 作为模型创建 ReAct 智能体
    query_agent = ReActAgent(
        name="Tom",
        sys_prompt=PROMPT['agentic_query_sys_prompt'],
        model=DashScopeChatModel(
            api_key=Config['API_KEY'],
            model_name=Config['MODEL'],
        ),
        formatter=DashScopeChatFormatter(),
        toolkit=toolkit,
    )

    msg_res = await query_agent(Msg("user", demand, "user"))

    return ToolResponse(
        content=msg_res.get_content_blocks("text"),
    )