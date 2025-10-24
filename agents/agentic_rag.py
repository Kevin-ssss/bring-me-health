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
from tools.build_sleep_vdbs import get_sleep_knowledge
from tools.build_heart_rate_vdbs import get_heart_rate_knowledge


async def agentic_rag(demand: str) -> ToolResponse:
    """
    将 RAG 模块与 ReActAgent 集成，实现对睡眠健康知识库和心率健康知识库的查询。
    目前该智能体支持查询睡眠健康和心率健康的专业知识，当需要时可以调用本工具函数。
    
    Args:
        demand (str):
            对知识库检索的需求。
    """
    
    # 创建工具箱
    toolkit = Toolkit()
    toolkit.register_tool_function(get_sleep_knowledge)
    toolkit.register_tool_function(get_heart_rate_knowledge)

    # 使用 DashScope 作为模型创建 ReAct 智能体
    rag_agent = ReActAgent(
        name="Jerry",
        sys_prompt=PROMPT['agentic_rag_sys_prompt'],
        model=DashScopeChatModel(
            api_key=Config['API_KEY'],
            model_name=Config['MODEL'],
        ),
        formatter=DashScopeChatFormatter(),
        toolkit=toolkit,
    )

    msg_res = await rag_agent(Msg("user", demand, "user"))

    return ToolResponse(
        content=msg_res.get_content_blocks("text"),
    )
    
