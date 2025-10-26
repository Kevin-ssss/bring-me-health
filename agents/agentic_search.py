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
from tools.web_search import web_search
from tools.pubmed_search import pubmed_search


# 模块级单例：避免每次调用都创建 Toolkit / ReActAgent
_search_toolkit = None
_search_agent = None

def _get_search_agent():
    """返回单例的 ReActAgent（惰性初始化）。"""
    global _search_toolkit, _search_agent
    if _search_agent is None:
        _search_toolkit = Toolkit()
        # 注册工具
        _search_toolkit.register_tool_function(web_search)
        _search_toolkit.register_tool_function(pubmed_search)

        # 使用 DashScope 作为模型创建 ReAct 智能体（只创建一次）
        _search_agent = ReActAgent(
            name="Sherlock",
            sys_prompt=PROMPT['agentic_search_sys_prompt'],
            model=DashScopeChatModel(
                api_key=Config['API_KEY'],
                model_name=Config['MODEL'],
            ),
            formatter=DashScopeChatFormatter(),
            toolkit=_search_toolkit,
        )
    return _search_agent


async def agentic_search(demand: str) -> ToolResponse:
    """
    将联网搜索模块与 ReActAgent 集成，实现互联网查询或在线文献库（PubMed）文献库检索的任务处理。
    该工具智能体负责接收来自路由智能体的任务，并根据任务内容选择合适的工具进行网页搜索，以获取最新的信息和资料。
    
    Args:
        demand (str):
            对联网搜索或查询在线文献库的需求。
    """
    # 使用模块级单例 agent（惰性初始化），避免重复构建模型和工具箱
    search_agent = _get_search_agent()

    msg_res = await search_agent(Msg("user", demand, "user"))

    return ToolResponse(
        content=msg_res.get_content_blocks("text"),
    )