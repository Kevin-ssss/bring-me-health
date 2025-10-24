import os
import sys

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

import dashscope
from langchain_qdrant import QdrantVectorStore
from langchain_dashscope import DashScopeEmbeddings
import hashlib
import json
from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import Config

def get_heart_rate_knowledge(demands: str,
                       pdf_dir: str = Config['HEART_RATE_PDF_PATH'], 
                       vdbs_path: str = Config['VDBS_PATH'], 
                       collection_name: str = Config['HEART_RATE_KNOWLEDGE_COLLECTION']) -> ToolResponse:
    """
    本工具构建/更新步数和心率健康知识库并根据demands获取retriever结果。
    当你需要查询步数和心率健康相关的专业知识时，可以调用本工具函数。

    Args:
        demands (str):
            对知识库检索的需求。
        pdf_dir (str):
            PDF 文件目录路径，已默认配置，调用工具时不需要提供。
        vdbs_path (str):
            向量数据库存储路径，已默认配置，调用工具时不需要提供。
        collection_name (str):
            向量数据库集合名称，已默认配置，调用工具时不需要提供。
    """

    pdfs = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    # 检查文件哈希值
    file_hashes = {}
    for fname in pdfs:
        path = os.path.join(pdf_dir, fname)
        with open(path, 'rb') as f:
            file_hashes[fname] = hashlib.sha256(f.read()).hexdigest()
    # 调取已有索引文件
    os.makedirs(vdbs_path, exist_ok=True)
    index_file = os.path.join(vdbs_path, 'indexed_files.json')
    if os.path.exists(index_file):
        build_database = False
        with open(index_file, 'r', encoding='utf-8') as f:
            indexed = set(json.load(f))
    else:
        indexed = set()
        build_database = True

    new_files = [fname for fname, h in file_hashes.items() if h not in indexed]

    # 定义嵌入模型
    dashscope.api_key = Config['API_KEY']
    embeddings = DashScopeEmbeddings(
        model=Config['EMBEDDING_MODEL'],  
    )

    if new_files:
        docs = []
        for fname in new_files:
            path = os.path.join(pdf_dir, fname)
            loader = PyPDFLoader(path)
            pages = loader.load()
            text = "".join(p.page_content for p in pages)
            splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
            chunks = splitter.create_documents([text])
            for c in chunks:
                c.metadata = c.metadata or {}
                c.metadata['source'] = path
                docs.append(c)
        
        if build_database:
            # 创建新的集合
            qdrant = QdrantVectorStore.from_documents(
                documents=docs,
                embedding=embeddings,
                collection_name=collection_name,
                path=vdbs_path,
                batch_size=10,
            )
        else: 
            # 在现有集合中添加文档
            qdrant = QdrantVectorStore.from_existing_collection(
                embedding=embeddings,
                collection_name=collection_name,
                path=vdbs_path,
            )
            qdrant.add_documents(documents=docs, batch_size=10)

        # 更新 index file
        indexed.update(file_hashes[f] for f in new_files)
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(list(indexed), f, ensure_ascii=False, indent=2)
    else:
        # 使用现成集合
        qdrant = QdrantVectorStore.from_existing_collection(
            embedding=embeddings,
            collection_name=collection_name,
            path=vdbs_path,
        )

    results = qdrant.similarity_search(demands, k=4)
    

    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=json.dumps({"metadata": results[0].metadata,"page_content": results[0].page_content}, ensure_ascii=False)
            ),
            TextBlock(
                type="text",
                text=json.dumps({"metadata": results[1].metadata,"page_content": results[1].page_content}, ensure_ascii=False)
            ),
            TextBlock(
                type="text",
                text=json.dumps({"metadata": results[2].metadata,"page_content": results[2].page_content}, ensure_ascii=False)
            ),
            TextBlock(
                type="text",
                text=json.dumps({"metadata": results[3].metadata,"page_content": results[3].page_content}, ensure_ascii=False)
            )
        ]
    )
