import os
import sys
import requests
import json
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import Config

def web_search(demand: str) -> ToolResponse:
    """
    使用 Bocha AI 提供的网页搜索 API，针对用户的查询需求进行网页搜索，并返回搜索结果。
    当你需要搜索获取全网相关信息时，可以调用本工具函数。
    
    Args:
        demand (str):
            用户的查询需求。
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

    response = requests.request("POST", Config['BOCHA_BASE_URL'], headers=headers, data=payload)

    # 获取网页搜索结果
    pages = response.json()['data']['webPages']['value']

    # 第一条 TextBlock：统计信息
    blocks = [
        TextBlock(
            type="text",
            text=f"已完成搜索，找到 {len(pages)} 条记录。"
        )
    ]

    # 循环生成每条结果
    for p in pages:
        blocks.append(
            TextBlock(
                type="text",
                text=f"标题: {p['name']}\n链接: {p['url']}\n摘要: {p['summary']}"
            )
        )

    return ToolResponse(content=blocks)
        


