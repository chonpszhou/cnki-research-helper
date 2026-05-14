# 技术原理 · CNKI研究助手

> 理解原理，才能更好地使用和调试

---

## 整体架构

```
┌──────────────────────────────────────────┐
│  Chrome（用户登录状态）                    │
│  用户输入账号 → 完成验证码 → 登录成功      │
│  Chrome Debug Port: 9222                │
└──────────────┬───────────────────────────┘
               │ WebSocket / CDP Protocol
               ▼
┌──────────────────────────────────────────┐
│  CDP Proxy (cdp-proxy.mjs)               │
│  HTTP REST API → WebSocket 命令           │
│  监听端口: 3456                          │
└──────────────┬───────────────────────────┘
               │ curl / Python requests
       ┌───────┴────────┐
       ▼                ▼
┌──────────────┐  ┌──────────────────┐
│ Python脚本    │  │ curl 直接下载    │
│ 控制浏览器    │  │ a.cnki.net PDF   │
│ 提取PDF链接  │  │ 公开，无需认证   │
└──────────────┘  └──────────────────┘
       │                │
       ▼                ▼
   PDF URL          .pdf 文件
       │
       ▼
   Obsidian 笔记
```

---

## 核心发现：PDF是公开的

知网有两层安全机制：

### 第一层：登录验证
- 滑动验证码（Tencent防水墙）
- 拦住自动化脚本登录
- **解决方案**：人手动登录一次，程序复用Cookie

### 第二层：详情页访问
- 直接HTTP请求（`requests.get`）访问论文详情页
- 知网返回安全验证页（2154字节，「安全验证」标题）
- **原因**：v=参数是短期签名，只能从浏览器导航中使用
- **解决方案**：用Chrome导航，程序提取PDF链接

### PDF文件本身
- `a.cnki.net/gw/api/get/pdf/ads/v1/pdf/{year}/{month}/{hash}.pdf`
- **无需任何认证**，curl直接下载
- hash为32位hex，无法从论文信息反向计算
- 必须通过Chrome访问详情页，从HTML提取

```
结论：
  登录验证（Cookie）→ Chrome导航详情页 → 提取PDF链接 → curl下载
  ↓
  PDF链接本身是完全公开的！
```

---

## CDP协议使用

Chrome DevTools Protocol (CDP) 是Chrome内置的调试接口：

| 命令 | 说明 |
|------|------|
| `Page.navigate` | 导航到URL |
| `Runtime.evaluate` | 执行JavaScript |
| `DOM.getDocument` | 获取页面DOM |

CDP Proxy（`cdp-proxy.mjs`）把这些WS命令转换为简单的HTTP GET请求：

```bash
# 导航到URL
curl "http://127.0.0.1:3456/navigate?target=<TAB>&url=<URL>"

# 执行JavaScript
curl -G "http://127.0.0.1:3456/eval" \
  --data-urlencode "target=<TAB>" \
  --data-urlencode "script=document.title"

# 获取所有标签页
curl "http://127.0.0.1:3456/targets"
```

---

## PDF URL提取原理

知网详情页的HTML中包含PDF下载链接：

```html
<a href="https://a.cnki.net/gw/api/get/pdf/ads/v1/pdf/2025/11/ead96fb14cd34cafab996ad47c89056b.pdf"
   target="_blank"
   onclick="...">
  PDF下载
</a>
```

提取方法：
```javascript
// 在CDP evaluate中执行
var html = document.body.innerHTML;
var matches = html.match(/a\.cnki\.net\/gw\/api\/get\/pdf\/[^\s"']+/g);
var pdfs = matches.filter(u => u.toLowerCase().includes('.pdf'));
return pdfs[0]; // 返回第一个PDF链接
```

---

## Cookie结构

知网Cookie包含两部分认证信息：

```
Ecp_LoginStuts={"IsAutoLogin":true,"UserName":"your_username",...}
cnkiUserKey=b458db20-5830-2471-4f43-b2c46aeb70c3
SID=...
```

- `Ecp_LoginStuts`：自动登录标记，包含用户名
- `cnkiUserKey`：用户密钥
- `SID`：会话ID

Cookie有效期约30天，过期后需要重新登录。

---

---

## ✅ 实战验证：搜索结果页提取法（2026-05-14）

> 这是目前最稳定的采集方式：**不进详情页，直接从搜索结果列表页提取元数据**。

### 核心发现

CNKI 的反爬验证只在**详情页**触发（`/kcms2/article/abstract?v=...`），而**搜索结果列表页**（`/kns8s/defaultresult/index`）可以直接访问，无验证码。

### URL 格式

```
# 搜索结果列表页（无需验证码）
https://kns.cnki.net/kns8s/defaultresult/index?kw=关键词&korder=SC

# 详情页（触发CAPTCHA，不可自动化）
https://kns.cnki.net/kcms2/article/abstract?v=签名参数...
```

### 操作流程

**Step 1：打开搜索结果页（需处理1次CAPTCHA）**
```bash
TARGET="<TAB_ID>"
curl "http://127.0.0.1:3456/navigate?target=${TARGET}&url=$(python3 -c 'import urllib.parse; print(urllib.parse.quote("https://kns.cnki.net/kns8s/defaultresult/index?kw=鄂尔多斯蒙古族文化&korder=SC"))')"
```

**Step 2：等待页面加载（约5秒）后提取元数据**
```javascript
// CDP eval：从搜索结果页提取全部论文元数据
(function(){
  var results = [];
  // 知网搜索结果列表结构
  var items = document.querySelectorAll('.result-list li, .article-list li, .brief-list li');
  if (items.length === 0) {
    // 备选选择器
    items = document.querySelectorAll('[class*="result"] li, [class*="article"] li');
  }
  items.forEach(function(li){
    var titleEl = li.querySelector('.title a, a.title, [class*="title"] a');
    var authorEl = li.querySelector('.author, [class*="author"]');
    var sourceEl = li.querySelector('.source, [class*="source"]');
    var yearEl = li.querySelector('.year, [class*="year"], [class*="date"]');
    var typeEl = li.querySelector('.db, [class*="type"], [class*="dbtype"]');
    if (titleEl) {
      results.push({
        title: titleEl.textContent.trim(),
        url: titleEl.href,
        author: authorEl ? authorEl.textContent.trim() : '',
        source: sourceEl ? sourceEl.textContent.trim() : '',
        year: yearEl ? yearEl.textContent.trim() : '',
        dbtype: typeEl ? typeEl.textContent.trim() : ''
      });
    }
  });
  return JSON.stringify({count: results.length, papers: results.slice(0, 10)});
})()
```

**Step 3：翻页采集**
```javascript
// 点击下一页按钮
var nextBtn = document.querySelector('.next, .page-next, [class*="next"], a:contains("下一页")');
if (nextBtn) { nextBtn.click(); }
```

### 实战结果（2026-05-14）

| 指标 | 数值 |
|------|------|
| 采集论文总数 | **151篇** |
| 期刊论文 | 92篇（特色期刊25 + 期刊67） |
| 学位论文 | 47篇（硕士45 + 博士2） |
| 会议论文 | 12篇 |
| 主题 | 鄂尔多斯蒙古族文化 |
| 采集耗时 | ~30分钟（含1次人工验证） |
| 入库方式 | Python脚本分类 → Obsidian笔记 |

### 元数据字段

搜索结果页可提取的字段：
- `title` — 论文标题
- `url` — 详情页URL（含v=签名参数）
- `author` — 作者
- `source` — 来源期刊/学校
- `year` — 发表年份
- `dbtype` — 类型（期刊/硕士/博士/会议）

⚠️ **注意**：搜索结果页**无摘要**，摘要需另外补充。

### 局限性

1. **无摘要**：搜索结果页只含标题/作者/来源，无摘要
2. **PDF不可下**：元数据≠PDF下载权限，PDF仍需登录态+机构订阅
3. **Cookie过期**：约2小时需重新登录
4. **搜索结果有限**：单次搜索最多4页（约80条），需变换关键词扩大覆盖

### 扩展方向

```python
# 多关键词扩展
keywords = [
    "鄂尔多斯蒙古族文化",
    "鄂尔多斯婚礼习俗",
    "鄂尔多斯蒙古族音乐",
    "鄂尔多斯蒙古族刺绣",
    "鄂尔多斯非物质文化遗产",
    "鄂尔多斯民歌",
]

# 批量采集 → papers.json → Obsidian分类 → 笔记双向链接
```

---

## 安全与隐私

| 方面 | 说明 |
|------|------|
| Cookie存储 | 本地文件 `~/.cnki_cookies.txt`，不在代码中 |
| 数据传输 | 仅本地Chrome进程，不经过第三方服务器 |
| PDF下载 | 直接访问知网服务器，无中间人 |
| 代码开源 | 所有逻辑透明可见，无后门 |

### 隐私建议
- 不要将Cookie文件提交到Git（`.gitignore`已配置）
- 定期清理下载的PDF（论文有版权，仅供研究）
- 机构账号Cookie不要分享给他人

---

## 性能优化

当前瓶颈：**网络延迟 + 页面渲染等待**

每篇论文处理时间：
- 详情页导航：~3秒（网络+服务器响应）
- 页面渲染等待：5秒（JavaScript动态加载）
- PDF URL提取：<1秒
- PDF下载：~2秒（取决于大小）

**理论速度**：约11秒/篇
**实测速度**：约5-8秒/篇（网络波动）

如需提速：
1. 减少等待时间（修改`sleep`参数）
2. 使用多Tab并行（需要修改脚本）
3. 批量下载时不要做其他网络操作
