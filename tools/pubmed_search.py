import asyncio
import json
from biomcp.articles.search import search_articles, PubmedRequest
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

async def pubmed_search(diseases: str, keywords: str = '') -> ToolResponse:
    """
    使用 BioMCP 提供的 PubMed 文章搜索功能，针对用户的查询需求进行文献检索，并返回搜索结果。
    当你需要搜索获取相关生物医学学术文章时，可以调用本工具函数。
    
    Args:
        demand (str):
            用户的查询需求。
    """
    article_request = PubmedRequest(
        diseases=[diseases],
        keywords=[keywords],
    )
    
    articles_result = await search_articles(article_request, output_json=True)
    articles_result = json.loads(articles_result)
    
    # 第一条 TextBlock：统计信息
    blocks = [
        TextBlock(
            type="text",
            text=f"已完成搜索，找到 {len(articles_result)} 篇文章。"
        )
    ]

    # 循环生成每条结果
    for p in articles_result:
        blocks.append(
            TextBlock(
                type="text",
                text=f"PMID: {p['pmid']}\n标题: {p['title']}\n期刊: {p['journal']}\n摘要: {p['abstract']}"
            )
        )

    return ToolResponse(
        content=blocks
    )
