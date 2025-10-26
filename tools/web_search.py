import os
import sys
import requests
import json
import asyncio
from typing import Callable
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import Config


def _web_search_sync(demand: str) -> ToolResponse:
    """
    同步实现的网页搜索请求（将在后台线程中执行以避免阻塞事件循环）。

    Args:
        demand (str): 搜索查询字符串。

    Returns:
        ToolResponse: 包含若干 TextBlock，第一条为统计信息，后续为每条搜索结果的标题/链接/摘要；出错时返回描述错误的 TextBlock。
    """
    payload = json.dumps({
        "query": demand,
        "summary": True,
        "count": 10
    })

    headers = {
        'Authorization': f"Bearer {Config['BOCHA_API_KEY']}",
        'Content-Type': 'application/json'
    }

    # 明确设置超时，避免长时间阻塞
    try:
        response = requests.post(Config['BOCHA_BASE_URL'], headers=headers, data=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        return ToolResponse(content=[TextBlock(type="text", text=f"网页搜索请求失败: {e}")])

    try:
        data = response.json()
        pages = data.get('data', {}).get('webPages', {}).get('value', [])
    except Exception as e:
        return ToolResponse(content=[TextBlock(type="text", text=f"解析搜索结果失败: {e}")])

    # 第一条 TextBlock：统计信息
    blocks = [TextBlock(type="text", text=f"已完成搜索，找到 {len(pages)} 条记录。")]

    # 循环生成每条结果（做必要的字段防护）
    for p in pages:
        title = p.get('name', '')
        url = p.get('url', '')
        summary = p.get('summary', '')
        blocks.append(TextBlock(type="text", text=f"标题: {title}\n链接: {url}\n摘要: {summary}"))

    return ToolResponse(content=blocks)


async def web_search(demand: str) -> ToolResponse:
    """
    异步包装的网页搜索工具函数。

    Args:
        demand (str): 搜索查询字符串。

    Returns:
        ToolResponse: 包含若干 TextBlock，第一条为统计信息，后续为每条搜索结果的标题/链接/摘要；出错时返回描述错误的 TextBlock。
    """
    # 使用 asyncio.to_thread 在默认线程池中运行同步请求
    return await asyncio.to_thread(_web_search_sync, demand)
        


