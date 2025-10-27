# 智能健康指导系统（IoT + RAG + Agent）

## 项目概要

本项目是一个面向个人健康数据（尤其是可穿戴设备产生的心率、睡眠等 IoT 数据）与专业文献的智能指导系统样例。系统由三大核心技术层结合而成：

- IoT（Internet of Things）：采集与接入个人设备产生的原始健康数据（如来自手环或手机的心率、睡眠记录、步数等），作为用户行为与生理信号的时间序列输入；
- RAG（Retrieval-Augmented Generation）：把与心率/睡眠相关的专业 PDF 文献构建为向量知识库（Vector DB），在用户咨询时检索最相关的知识片段，为生成回答提供事实依据与可追溯的证据；
- Agent（基于 Agentscope）：使用 ReAct 风格的智能代理框架，把用户查询路由到适当的工具（检索、查询本地数据、或生成多模态输出），并在需要时执行代码、生成音频或调用外部工具。

主要功能：

- 数据接入：解析和标准化来自设备或本地数据库（示例中为 Gadgetbridge.db）中的心率与睡眠数据；
- 知识构建：将 PDF 文档（睡眠/心率相关）通过文本抽取、分块和 embedding，构建/更新 Qdrant 向量数据库；
- 检索增强对话：在用户提出健康相关问题时，Agent 自动检索最相关的知识片段并将其作为上下文，辅助生成更可靠的答案；
- 工具化路由：Agent 可组合多个工具（如 RAG 检索、query 数据库、输出处理），支持可扩展的交互能力；
- 可扩展输出：支持将工具结果格式化为对话文本，也可调用执行代码或生成音频等扩展工具能力。

## 目录结构

- `app.py` — Quart 应用入口，创建应用实例并注册路由蓝本（`router/chat.py`）；用于本地 demo 和 API 调试。
- `config.py` — 全局配置（示例字典）。包含模型、embedding 配置、向量库路径、PDF 目录和数据库路径等。建议生产环境改为环境变量或密钥管理服务。
- `prompt.py` — 系统与工具的 Prompt 模板集合，用于驱动 Agentscope Agent 的系统提示与工具调用行为。
- `router/`
  - `chat.py` — 与前端/HTTP 层交互的路由实现，接收用户请求并调用内部路由 Agent 返回流式或完整响应。
- `agents/`
  - `router_agent.py` — 用于将用户请求拆解并路由到不同工具的 ReAct Agent 实现，注册工具并驱动 Agent 生命周期。
  - `agentic_rag.py` — RAG 工具实现：包装对向量数据库的检索逻辑，并把检索结果以 `ToolResponse` 的形式返回给 Agent。
  - `agentic_query.py` — 针对本地结构化数据（如 SQLite、Gadgetbridge.db）或其他数据源的查询工具。
  - `agentic_output.py` — 把工具输出格式化为对话消息，支持额外功能（代码执行、文本转语音等）。
- `tools/`
  - `build_sleep_vdbs.py` — 把 `data/document/sleep/` 下的 PDF 转为 embedding 并写入 Qdrant 向量库；包含索引去重逻辑（基于文件哈希）。
  - `build_heart_rate_vdbs.py` — 同上但针对心率文档目录。
  - `parse_sleep_db.py` — 解析 wearable/手环的睡眠数据文件（数据库），提取时间序列与事件。
  - `parse_heart_rate_db.py` — 解析心率相关的数据库或存档，输出结构化时间序列。
- `data/`
  - `document/` — 存放用于构建知识库的 PDF 文档（子目录：`sleep/`、`heart_rate/`）。
  - `vdbs/` — 向量数据库与索引文件（如 `indexed_files.json`），由构建脚本生成与维护。
  - `user_data/` — 示例或导入的设备本地数据库（例如 `Gadgetbridge.db`）。
- `static/`, `templates/` — 前端静态资源与模板（如果使用 web 界面）。

## 技术栈

本项目的选型旨在实现一个可扩展、模块化的 RAG + Agent 平台，适用于 IoT 数据融合与文献增强的问答场景：

- Python 3.8+/3.10+: 作为主开发语言，生态丰富，便于集成各类 ML/AI 库与数据库驱动。
- Agentscope: 提供基于 ReAct 的 Agent 架构与工具接口（用于组合检索、查询、输出等功能），便于将复杂的对话流程分解为工具调用与决策步骤。
- DashScope: 作为模型与 embedding 的服务提供者（示例中用于生成文本与 embedding）；如果组织使用其他大模型服务（OpenAI、Anthropic、Qwen 等），也可替换 embedding 与模型实现层。
- LangChain 与相关 Loader/Splitter: 用于 PDF 文本抽取、分块与文档到向量的流水线构建（`PyPDFLoader`、`RecursiveCharacterTextSplitter` 等）。
- Qdrant: 向量数据库用于存储文档 embeddings，支持相似度检索（local filesystem-backed 或 qdrant server，取决于部署方式）。
- Sqlite: 通过 `sqlite3`、自定义解析脚本将 Wearable 数据（如 Gadgetbridge 或手环导出的 DB）转换为可查询的结构化数据。
- Quart: 使用 Quart 提供异步 HTTP 接口，支持流式响应（例如将 Agent 的生成分片推送到前端）。
- 可扩展工具链: Agentscope 的 `Toolkit` 抽象允许注册外部工具（执行 shell、执行 Python 代码、生成音频等），便于把平台扩展成多模态的自动化系统。

## Questions Example

- 我现在的睡眠情况如何？帮我分析一下我的睡眠数据，并结合相关专业知识提供健康建议。
- 请全网搜索，看看当代大学生平均睡眠情况怎么样？
- 请查阅pubmed专业文献，看看失眠主要由哪些因素导致？
- 请基于我的数据库，看看我的睡眠情况属于当代大学生的什么水平？
- 我现在的睡眠质量如何？请帮我画图展示一下我各个睡眠指标的情况，自动运行代码并将图片保存到本地。
- 我现在的睡眠质量如何？请用一句话总结一下，并转为音频文件保存到本地。

## TODO

短期可实现：

- ✅把向量数据库改为本地存储并实现增量更新
- ✅搭建 Quart API 框架
- ✅增强提示词工程以提高 Agent 的输出质量
- ✅封装构建脚本为可执行文件
- ✅优化前端与网络缓存以防止堵塞、加速响应（如选用轻量化模型或提示简化）
- ✅增加用于生成 output 的智能体以支持多模态输出
- 将pdf转markdown后导入向量数据库（MinerU或MarkItDown）
- 加入USER_ACCOUNT储存用户画像和用户数据（本地/在线mysql）
- 加入长期记忆和对话记录（agentscope memory模块）
- ✅调用pubmed接口获取相关领域的文献摘要（如biomcp）
- ✅添加联网搜索功能（如searXNG引擎、博查API）
- 自然语言生成SQL语句（如DAIL-SQL算法），调用工具来获取对应数据库的数据
- 桌面应用程序（PyQt or PySide or Electron）

中长期目标：

* 远程连接可穿戴设备数据库
* 用户端与管理端分离（用户管理系统）
* PC端与手机端多端同步

## Quickly Start

项目现在提供一个本地启动器 `launcher.py`：它会在后台启动 Quart 服务并在加载 `http://127.0.0.1:5000/`。

方式一：运行launcher.ps1文件（确保已经安装python）

方式二：打包运行

- 安装依赖（建议在虚拟环境中运行）：

```powershell
pip install -r requirements.txt
```

基本运行（开发/调试）

```powershell
python .\launcher.py
```

使用 PyInstaller 打包示例命令（Windows PowerShell）：

```powershell
pyinstaller -F launcher.py --onedir -i icon.ico --add-data "templates;templates"  --add-data "static;static"
```

使用 Nuitka 打包示例命令

```powershell
python -m nuitka --standalone --output-dir=dist_nuitka --include-package=quart --include-data-dir=templates=templates --include-data-dir=static=static --enable-plugin=no-qt launcher.py
```

## Output Sample

User: 我现在的睡眠情况如何？帮我分析一下我的睡眠数据，并结合相关专业知识提供健康建议。

Alice:  你好！我已帮你分析了最近的睡眠数据，并结合专业医学资料为你整理了以下内容～ 🌙

---

### 📊 你的睡眠数据概览（2025-10-24）：

- **总睡眠时长**：8小时24分钟（504分钟）✅
- **入睡时间**：凌晨1:45
- **醒来时间**：上午10:17
- **睡眠评分**：82/100（良好）
- **睡眠结构**：
  - **深睡**：29.17%（正常范围：15%~20%）⚠️偏高
  - **浅睡**：43.65%（正常范围：55%~70%）⚠️偏低
  - **REM睡眠**：27.18%（正常范围：20%~25%）⚠️略高

---

### ⚠️ 专业解读：

你的总睡眠时长充足，但**睡眠结构比例异常**，不符合健康成年人的典型模式。这种“深睡过多、浅睡过少、REM偏高”的组合，可能提示存在以下潜在问题：

#### 可能原因包括：

1. **药物影响**：如抗抑郁药、镇静剂或某些抗癫痫药可能人为增加深睡。
2. **睡眠呼吸暂停（OSAHS）**：夜间缺氧可能导致身体“代偿性”延长深睡。
3. **神经系统疾病**：如帕金森病、阿尔茨海默病早期可能影响睡眠结构。
4. **心理因素**：严重抑郁或焦虑在特定治疗下也可能改变睡眠阶段分布。
5. **长期疲劳后的恢复性睡眠**：身体在极度疲惫后可能暂时增加深睡。

---

### 💡 健康建议：

✅ **立即行动**：

- 如果你正在服用任何精神类、镇静类或抗癫痫药物，请**咨询医生**是否影响睡眠。
- 开始记录**睡眠日志**（入睡/醒来时间、夜间醒来次数、白天精神状态等）。

✅ **建议就医检查**：

- **多导睡眠图（PSG）**：这是诊断睡眠障碍的“金标准”，能准确判断是否存在呼吸暂停、肢体运动障碍等问题。
- 如有记忆力下降、手抖、情绪低落等症状，建议转诊**神经科或精神科**。

✅ **生活方式调整**：

- 保持规律作息，尽量在**晚上11点前入睡**（你目前入睡偏晚）；
- 睡前避免酒精、咖啡因；
- 白天适度运动，但避免睡前剧烈活动；
- 营造安静、黑暗、凉爽的睡眠环境。

---

### ❤️ 温馨提醒：

虽然你的睡眠评分看起来不错，但**睡眠结构异常可能是身体发出的早期信号**！别忽视它～
建议尽早进行专业评估，早发现、早干预，才能睡得更安心、更健康！💤

需要我帮你生成一份睡眠日志模板或预约检查建议吗？随时告诉我哦！(•̀ᴗ•́)و**
