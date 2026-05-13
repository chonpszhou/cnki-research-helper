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
Ecp_LoginStuts={"IsAutoLogin":true,"UserName":"lydl08",...}
cnkiUserKey=b458db20-5830-2471-4f43-b2c46aeb70c3
SID=...
```

- `Ecp_LoginStuts`：自动登录标记，包含用户名
- `cnkiUserKey`：用户密钥
- `SID`：会话ID

Cookie有效期约30天，过期后需要重新登录。

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
