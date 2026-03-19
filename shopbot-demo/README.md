# ShopBot - 智能购物助手

基于 LangGraph + AWS Bedrock Claude Sonnet 4.5 的电商购物 Agent Demo。

## 项目概述

ShopBot 是一个智能购物助手，使用单一 AI Agent 配合 17 个工具来帮助用户完成购物任务。支持商品搜索、购物车管理、价格追踪、用户偏好学习等功能。

### 核心特性

- **单一智能体架构**：一个 Agent + 17 个工具，ReAct 循环自主决策
- **会话持久化**：基于 SQLite 的 LangGraph Checkpointer
- **用户画像系统**：自动学习用户偏好（后台更新机制）
- **Context 自动压缩**：800K token 阈值，智能摘要 + 保留最近消息
- **流式响应**：SSE (Server-Sent Events) 实时输出
- **Prompt Caching**：多 cache block 策略优化性能
- **可观测性**：集成 LangFuse 平台（可选）

## 技术栈

- **框架**：LangGraph (LangChain)
- **LLM**：AWS Bedrock Claude Sonnet 4.5
- **API**：FastAPI + Uvicorn
- **持久化**：SQLite (langgraph-checkpoint-sqlite)
- **数据**：Mock JSON 文件

## 项目结构

```
shopbot/
├── app/
│   ├── main.py                 # FastAPI 应用入口
│   ├── agent.py                # LangGraph Agent 定义
│   ├── background_profile_updater.py  # 后台画像更新
│   ├── models/
│   │   ├── state.py            # ShopBotState 定义
│   │   ├── data.py             # Pydantic 数据模型
│   │   └── persistence.py      # Checkpointer 配置
│   └── tools/
│       ├── shopping_tools.py   # 商品搜索/详情工具
│       ├── cart_tools.py       # 购物车管理工具
│       ├── other_tools.py      # 历史/偏好/价格工具
│       └── context_tools.py    # Context 管理工具
├── data/
│   ├── products.json           # 商品数据 (20 items)
│   ├── products_display.json   # 前端展示数据
│   ├── users.json              # 用户数据 (3 users)
│   ├── user_profiles/          # 用户画像目录
│   └── shopbot.db              # 会话持久化数据库
├── frontend/
│   ├── index.html              # Web 前端
│   └── images/                 # 商品图片
├── logs/                       # LLM 日志
└── requirements.txt            # Python 依赖

```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# AWS Bedrock 配置
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-5-20250929-v1:0

# 可选：LangFuse 观测
ENABLE_LANGFUSE=false
# LANGFUSE_PUBLIC_KEY=pk-xxx
# LANGFUSE_SECRET_KEY=sk-xxx
# LANGFUSE_HOST=https://cloud.langfuse.com
```

### 3. 启动服务

```bash
# 方式 1: 直接运行
python -m uvicorn app.main:api --reload --port 8000

# 方式 2: 使用脚本（推荐）
./start_shopbot_web.sh
```

服务启动后：
- API: http://localhost:8000
- 前端: http://localhost:8000/app/
- API 文档: http://localhost:8000/docs

## API 端点

### 聊天相关

- `POST /chat` - 非流式聊天
  ```json
  {
    "message": "帮我找一款笔记本电脑",
    "user_id": "user_001",
    "session_id": "session_xxx"  // 可选
  }
  ```

- `POST /chat/stream` - SSE 流式聊天
  - 返回 Server-Sent Events 流
  - 事件类型：`content`, `tool_start`, `tool_end`, `done`, `error`

- `GET /history/{session_id}` - 获取会话历史

- `DELETE /session/{session_id}` - 删除会话

### 商品相关

- `GET /api/products` - 获取商品列表
- `GET /api/suggested-questions/{product_id}` - 生成商品推荐问题

### 用户相关

- `GET /user/{user_id}/preferences` - 获取用户偏好
- `PUT /user/{user_id}/preferences` - 更新用户偏好

### 健康检查

- `GET /health` - 健康检查

## 核心功能

### 1. 17 个工具

**商品相关 (3)**
- `search_products` - 搜索商品
- `get_product_details` - 获取单个商品详情
- `get_products_batch` - 批量获取商品详情

**购物车 (4)**
- `add_to_cart` - 添加到购物车
- `get_cart` - 查看购物车
- `remove_from_cart` - 从购物车移除
- `checkout` - 结账

**其他 (10)**
- `get_purchase_history` - 查看购买历史
- `get_wishlist` / `add_to_wishlist` / `remove_from_wishlist` - 愿望清单
- `get_user_preferences` - 获取用户偏好
- `get_price_history` / `set_price_alert` - 价格追踪
- `get_product_reviews` - 商品评论
- `archive_previous_conversation` - 对话归档

### 2. 用户画像系统

用户画像存储在 `data/user_profiles/{user_id}.json`，包含 5 个字段：

- `explicit_preferences` - 用户明确说明的偏好
- `inferred_preferences` - 从行为推断的偏好
- `stylistic_notes` - 沟通风格和习惯
- `successful_patterns` - 成功经验
- `things_to_avoid` - 失败经验（需要避免的）

**后台更新机制：**
- 用户 idle 30 秒后触发（测试用，生产环境建议 30 分钟）
- 使用 LLM 分析最近对话，更新画像
- 采用增量更新策略（不覆盖现有内容）

### 3. Context 自动压缩

**触发条件：**
- Token 数 > 800K（使用 tiktoken 精确计数）

**压缩策略：**
1. 生成对话摘要（保留关键信息）
2. 删除旧消息，保留最近 10 条
3. 摘要注入 System Prompt，供后续对话使用

**Agent 主动归档：**
- Agent 可以调用 `archive_previous_conversation` 工具主动归档
- 优先级高于被动压缩（800K 兜底机制）

### 4. Prompt Caching 优化

使用多 cache block 策略减少成本：

- **Block 1**: System Prompt（永不变，100% 缓存）
- **Block 2**: 用户画像（很少变，95% 缓存）
- **Block 3**: 确认消息（永不变，100% 缓存）
- **Block 4**: 当前对话（每次都变，不缓存）

## 日志和调试

### LLM 日志

所有 LLM 输入/输出记录在 `logs/llm_YYYYMMDD.log`：

```
🔵 [LLM INPUT] Session: xxx, User: xxx
Message [1] - Type: system
Content: 你是智能购物助手 ShopBot...
----------------------------------------
🟢 [LLM OUTPUT] Session: xxx, User: xxx
Content: 我帮您找到以下商品...
Tool Calls (2): search_products, get_product_details
```

### LangFuse 观测（可选）

设置环境变量启用：

```bash
ENABLE_LANGFUSE=true
LANGFUSE_PUBLIC_KEY=pk-xxx
LANGFUSE_SECRET_KEY=sk-xxx
```

## 测试

### 测试用户

系统预设 3 个测试用户（`data/users.json`）：

- `user_001` - Alice（科技爱好者）
- `user_002` - Bob（家居达人）
- `user_003` - Charlie（运动健身）

### 示例对话

```bash
# 启动服务后，访问前端
open http://localhost:8000/app/

# 或使用 API
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "帮我找一款适合跑步的鞋子",
    "user_id": "user_001"
  }'
```

## 设计亮点

1. **单一智能体 + 工具集**：简洁架构，避免多 Agent 复杂性
2. **ReAct 循环**：Agent 自主推理、调用工具、循环迭代
3. **TypedDict State**：类型安全，自定义 reducer 过滤中间消息
4. **用户画像注入**：动态 System Prompt，个性化体验
5. **Context 自动管理**：无需担心 token 限制，支持长对话
6. **流式响应**：SSE 实时输出，优化用户体验
7. **Mock 数据**：快速原型验证，可替换为真实数据源

## 生产环境建议

- [ ] 替换 Mock JSON 为真实数据库（PostgreSQL/MySQL）
- [ ] 实现真实的用户认证和授权
- [ ] 配置 CORS 限制为具体域名
- [ ] 优化 SQLite 为生产级数据库（PostgreSQL）
- [ ] 添加缓存层（Redis）
- [ ] 监控和告警（Prometheus/Grafana）
- [ ] 负载均衡和水平扩展

## License

MIT
