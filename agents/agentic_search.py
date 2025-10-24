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

async def agentic_search(demand: str) -> ToolResponse:
    """
    将联网搜索模块与 ReActAgent 集成，实现互联网查询或在线文献库（PubMed）文献库检索的任务处理。
    该工具智能体负责接收来自路由智能体的任务，并根据任务内容选择合适的工具进行网页搜索，以获取最新的信息和资料。
    
    Args:
        demand (str):
            对联网搜索或查询在线文献库的需求。
    """
    # 创建工具箱
    toolkit = Toolkit()
    toolkit.register_tool_function(web_search)
    toolkit.register_tool_function(pubmed_search)

    # 使用 DashScope 作为模型创建 ReAct 智能体
    search_agent = ReActAgent(
        name="Sherlock",
        sys_prompt=PROMPT['agentic_search_sys_prompt'],
        model=DashScopeChatModel(
            api_key=Config['API_KEY'],
            model_name=Config['MODEL'],
        ),
        formatter=DashScopeChatFormatter(),
        toolkit=toolkit,
    )

    msg_res = await search_agent(Msg("user", demand, "user"))

    return ToolResponse(
        content=msg_res.get_content_blocks("text"),
    )