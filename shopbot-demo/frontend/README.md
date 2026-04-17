# ShopBot 前端使用指南

## 概述

这是 ShopBot 的前端界面，采用纯 HTML + Tailwind CSS + Vanilla JS 开发，实现了现代化的电商购物体验 + AI 聊天助手。

## 功能特性

### 🛍️ **电商展示**
- 商品卡片网格布局
- 商品信息完整展示（图片、标题、价格、评分、库存）
- 悬停动画效果
- 折扣标签显示

### 🤖 **ShopBot 聊天**
- 实时聊天交互
- 流式响应（SSE）
- 推荐问题 chips
- 商品上下文感知

### ✨ **智能交互**
- 点击商品自动生成推荐问题
- 一键发送推荐问题
- 商品高亮选中
- 自动滚动到底部

---

## 文件结构

```
frontend/
├── index.html       # 主页面（布局 + 样式）
├── app.js           # 前端逻辑（API 调用、事件处理）
└── README.md        # 本文档
```

---

## 快速开始

### 1. 启动后端

```bash
cd /home/ubuntu/project/shopbot
python -m uvicorn app.main:api --reload --host 0.0.0.0 --port 8000
```

### 2. 访问前端

#### 方法 A: 通过 FastAPI 静态文件服务
```
http://localhost:8000/app/index.html
```

#### 方法 B: 使用 Python 简单服务器
```bash
cd frontend
python -m http.server 3000
```
然后访问 `http://localhost:3000`

---

## API 端点

前端调用以下后端 API：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/products` | GET | 获取商品列表 |
| `/api/suggested-questions/{product_id}` | GET | 获取推荐问题 |
| `/chat/stream` | POST | 发送消息（流式响应） |

---

## 核心流程

### 1. 商品点击流程

```
用户点击商品
  ↓
前端：高亮选中 + 更新 current_product_context
  ↓
调用 /api/suggested-questions/{product_id}
  ↓
后端：使用 LLM 生成 5 个推荐问题
  ↓
前端：显示 question chips
  ↓
用户点击 chip
  ↓
发送问题到 /chat/stream
  ↓
流式显示 AI 响应
```

### 2. 消息发送流程

```
用户输入消息
  ↓
前端：addUserMessage()
  ↓
调用 /chat/stream (POST)
  body: {
    message: "...",
    user_id: "...",
    session_id: "...",
    current_product_context: "prod_001"  // 如果有
  }
  ↓
后端：Agent 处理（ReAct 循环）
  ↓
返回 SSE 流：
  data: {"type": "token", "content": "..."}
  data: {"type": "tool_start", "tool": "search_products"}
  data: {"type": "token", "content": "..."}
  data: {"type": "done"}
  ↓
前端：逐 token 显示（打字效果）
```

---

## 配置

### API 地址

在 `app.js` 中修改：

```javascript
const APP_STATE = {
    apiBaseUrl: 'http://localhost:8000'  // 修改为你的后端地址
};
```

### 样式自定义

在 `index.html` 的 `<style>` 标签中修改：

- 颜色渐变：`.bg-gradient-to-r from-purple-500 to-pink-500`
- 悬停效果：`.product-card:hover`
- 动画效果：`@keyframes slideIn`

---

## 技术细节

### SSE (Server-Sent Events) 流式响应

```javascript
// 1. 发送 POST 请求
const response = await fetch('/chat/stream', {
    method: 'POST',
    body: JSON.stringify(...)
});

// 2. 获取 ReadableStream
const stream = response.body;
const reader = stream.getReader();

// 3. 逐块读取
while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    // 4. 解码并处理
    const chunk = decoder.decode(value);
    // 解析 SSE 格式：data: {...}\n\n
}
```

### 商品卡片动态渲染

```javascript
function createProductCard(product) {
    const card = document.createElement('div');
    card.innerHTML = `...`;  // 模板字符串
    card.addEventListener('click', () => handleProductClick(product));
    return card;
}
```

---

## 浏览器兼容性

- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

依赖的现代特性：
- Fetch API
- ReadableStream
- ES6+ (async/await, arrow functions, template literals)
- CSS Grid
- Flexbox

---

## 常见问题

### Q1: CORS 错误

**问题**: `Access-Control-Allow-Origin` 错误

**解决**: 后端已配置 CORS 中间件，确保后端正在运行

### Q2: 商品不显示

**问题**: 商品网格一直显示"加载中"

**解决**:
1. 检查 `/api/products` 端点是否正常
2. 检查 `data/products_display.json` 文件是否存在
3. 打开浏览器控制台查看错误

### Q3: 聊天无响应

**问题**: 发送消息后没有回复

**解决**:
1. 检查 `/chat/stream` 端点是否正常
2. 检查 AWS 凭证配置
3. 查看后端日志

### Q4: 推荐问题不显示

**问题**: 点击商品后没有推荐问题

**解决**:
1. 检查 `/api/suggested-questions/{product_id}` 端点
2. 查看浏览器控制台网络请求
3. 后端会返回默认问题作为回退

---

## 开发建议

### 1. 本地开发

使用浏览器开发者工具：
- **Network** 标签：查看 API 请求
- **Console** 标签：查看 JavaScript 错误
- **Application** 标签：查看 LocalStorage

### 2. 调试技巧

在 `app.js` 中添加日志：

```javascript
console.log('点击商品:', product.id);
console.log('API 响应:', data);
```

### 3. 性能优化

- 减少不必要的重渲染
- 使用防抖（debounce）处理高频事件
- 图片懒加载

---

## 下一步

### 功能扩展

- [ ] 添加商品搜索过滤
- [ ] 实现购物车功能

---

## 参考资源

- [Tailwind CSS 文档](https://tailwindcss.com/docs)
- [Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API)
- [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [FastAPI 文档](https://fastapi.tiangolo.com/)

---

## 许可证

MIT License
