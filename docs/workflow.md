# CNKI研究助手 - 完整工作流程

> 深入理解工具背后的原理，适合二次开发和问题排查

---

## 整体架构

```
┌─────────────────────────────────────────────────────────┐
│  Chrome Debug Port (9222)                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Debug Chrome（用户登录状态）                       │  │
│  │  已登录CNKI账号                                    │  │
│  │  - 搜索结果渲染                                   │  │
│  │  - 论文详情页渲染（含PDF链接）                     │  │
│  └───────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │ CDP Protocol
                        ▼
┌───────────────────────────────────────────────────────────┐
│  CDP Proxy (3456)                                        │
│  HTTP REST API: /navigate, /eval, /targets, /health      │
│  作用：将HTTP请求转换为Chrome CDP WebSocket命令            │
└───────────────────────┬───────────────────────────────────┘
                        │
          ┌─────────────┴──────────────┐
          ▼                            ▼
┌─────────────────┐        ┌─────────────────────────┐
│ cnki_downloader │        │ curl / requests        │
│ (Python + CDP)   │        │ (PDF直接下载，公开)     │
│ 自动化控制浏览器  │        │ a.cnki.net 无需认证    │
└────────┬────────┘        └────────────┬────────────┘
         │                             │
         ▼                             ▼
    提取PDF URL               保存到本地 .pdf 文件
         │
         ▼
  Obsidian笔记生成
  （可选）
```

---

## 技术原理

### 1. CDP (Chrome DevTools Protocol)

Chrome提供调试接口，通过WebSocket暴露给外部。
常用命令：
- `Page.navigate` — 导航到URL
- `Runtime.evaluate` — 执行JavaScript代码
- `DOM.getDocument` — 获取页面DOM结构

CDP Proxy（`cdp-proxy.mjs`）把这些WS命令转换为HTTP REST API，
让你可以用`curl`控制Chrome，无需写WebSocket客户端。

### 2. CNKI安全机制分析

```
直接HTTP请求（requests/curl）
    │
    ▼
CNKI服务器
    │
    ├─ GET /kns8s/defaultresult → 200 ✅（搜索页）
    │
    └─ GET /kcms2/article/abstract?v=xxx
           │
           ├─ 检测到v=参数来自直接请求（非浏览器导航）
           │
           ▼
           重定向到 /verify/（Tencent防水墙）
           返回: <title>安全验证</title>, 2154字节
           └─ Python requests → 只能拿到验证页HTML，无法继续
```

**关键发现**：
- `a.cnki.net/gw/api/get/pdf/...` 的PDF文件**完全公开**
- 知网的安全验证只保护"进入论文详情页"的过程
- 一旦进入详情页（浏览器中），PDF链接是公开的
- 所以正确流程：**浏览器导航获取PDF URL → curl下载PDF**

### 3. PDF URL格式解析

```
https://a.cnki.net/gw/api/get/pdf/ads/v1/pdf/{year}/{month}/{hash32}.pdf

示例：
https://a.cnki.net/gw/api/get/pdf/ads/v1/pdf/2025/11/ead96fb14cd34cafab996ad47c89056b.pdf

字段说明：
  year  — 论文发表年份
  month — 论文发表月份
  hash32 — 32位hex，疑似论文特征码，无法反向计算
           必须通过访问详情页从HTML提取
```

---

## 搜索策略

### 按主题搜索
```bash
python3 scripts/cnki_downloader.py -k "储能" -p 3          # 储能
python3 scripts/cnki_downloader.py -k "碳达峰 碳中和" -p 2  # 双碳
python3 scripts/cnki_downloader.py -k "分布式光伏" -p 2      # 光伏
```

### 按文献类型筛选
```bash
-t journal    # 仅期刊论文（有PDF）
-t newspaper  # 仅报纸文章（无PDF，仅CAJ）
-t all        # 全部（默认）
```

### 按发表时间筛选（需修改脚本）
在搜索URL中添加时间参数：
```
https://kns.cnki.net/kns8s/defaultresult/index?kw=关键词&kdfrom=2023&kdto=2025
```

---

## 隐私与安全

### 本工具会收集什么？
- 搜索关键词（保存在本地JSON文件中）
- 论文URL和标题（保存在本地）
- PDF文件（下载到本地目录）

### 本工具不会收集什么？
- ❌ CNKI账号密码（你手动输入，从不经过本工具）
- ❌ Cookie内容（本工具只读取你指定的文件）
- ❌ 任何数据上传到外部服务器

### 隐私建议
1. **不要将Cookie文件提交到Git** — 已通过`.gitignore`忽略
2. Cookie文件放在`~/.cnki_cookies.txt`（用户目录），不放在项目目录
3. 定期清理下载的PDF（知网论文有版权，仅供个人研究）

---

## 二次开发

### 添加新的论文信息字段

修改 `cnki_downloader.py` 中的 `get_search_results()` 函数，
在JavaScript提取部分添加更多字段：

```python
js = r"""(function(){
  ...
  r.push({
    seq:     cells[0].textContent.trim(),
    title:   link.textContent.trim().slice(0, 80),
    url:     link.href,
    source:  cells.length > 2 ? cells[2].textContent.trim().replace(/\s+/g,'') : '',
    date:    cells.length > 3 ? cells[3].textContent.trim() : '',
    dbtype:  cells.length > 4 ? cells[4].textContent.trim() : '',
    // 新增字段：
    cited:   cells.length > 6 ? cells[6].textContent.trim() : '',  // 被引次数
    // ...
  });
  ...
})()"""
```

### 集成Obsidian笔记生成

运行 `extract_notes.py`（需要`pip install obsidiantools`或类似库）：
```bash
python3 scripts/extract_notes.py --pdf-dir ./downloads --vault /path/to/your/vault
```

---

## 故障排查

| 症状 | 可能原因 | 解决方法 |
|------|----------|----------|
| `curl: (7) Failed to connect` | Chrome Debug未启动 | 重新运行Chrome启动命令 |
| `{"error":"invalid target"}` | Tab ID无效/过期 | 刷新Tab：`curl -s http://127.0.0.1:3456/targets` |
| 搜索结果为0 | 搜索词无结果或页面未加载 | 增加`sleep`时间，或手动检查页面 |
| PDF下载是错误页 | PDF URL已过期（v=失效） | 重新从搜索结果获取最新URL |
| `SyntaxError` in JS | Python字符串引号嵌套问题 | 使用raw string `r"""..."""` |
