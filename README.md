<!-- CNKI研究助手 - 让人人都能批量下论文 -->

<div align="center">

# 🔓 CNKI研究助手

**知网论文 · 批量下载 · REST API · 学术写作工具**

*「发现知网PDF竟然公开可下，激动得差点从椅子上摔下来」*

[![MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-green.svg)]()
[![Node.js](https://img.shields.io/badge/Node.js-16+-yellow.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-cyan.svg)]()
[![paper-ai](https://img.shields.io/badge/paper--ai-v1.0+-orange.svg)]()

*中文项目 · 开源免费 · 完全本地*

</div>

---

## 💡 这个工具解决什么问题？

知网单篇下载 **2-20元**，会员月卡 **30元**，机构账号还得挂VPN。

直到我们逆向发现：**知网的PDF文件根本就是公开的** 🎉

```
a.cnki.net/gw/api/get/pdf/ads/v1/pdf/2025/11/xxxxx.pdf
```

安全验证只是「门卫」——拦住自动化请求，但不妨碍真实用户。

这个工具就是：**用Chrome替你过门卫 → 批量拿到PDF → AI写作工具直接引用**

---

## ⚡ 30秒上手（一键启动）

```bash
# 克隆项目
git clone https://github.com/chonpszhou/cnki-research-helper.git
cd cnki-research-helper

# 一键启动（Chrome + CDP Proxy + API 服务）
chmod +x start.sh
./start.sh

# 打开浏览器登录（首次只需一次）
open https://login.cnki.net/
```

然后访问 [paper-ai](https://github.com/chonpszhou/paper-ai)，在论文来源中选择 **CNKI知网** 即可。

---

## ⚡ 30秒上手（独立使用）

### 1. 启动专用Chrome

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome-Debug-CNKI" \
  --no-first-run --no-default-browser-check &
```

### 2. 启动代理

```bash
cd ~/cnki-research-helper
node scripts/cdp-proxy.mjs 3456 9222 &
```

### 3. 手动登录知网（一次性）

在Chrome窗口里打开 → `https://login.cnki.net/` → 登录你的账号

### 4. 开始使用（二选一）

**方式A：命令行下载**
```bash
python3 scripts/cnki_downloader.py -k "算电协同" -p 2
```

**方式B：REST API（供其他工具调用）**
```bash
python3 scripts/cnki_api.py --port 8080 &
curl "http://localhost:8080/search?kw=算电协同&pages=1"
```

---

## 🏗️ 架构说明

```
┌─────────────────────────────────────────────────────────┐
│  用户浏览器                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────┐  │
│  │  paper-ai   │    │  Claude/CLI  │    │  命令行下载  │  │
│  │  (Next.js)  │    │  (任意AI工具) │    │ cnki_down- │  │
│  └──────┬──────┘    └──────┬───────┘    │  loader.py  │  │
│         │                  │             └──────┬─────┘  │
│         └────────┬─────────┘──────────────────┘         │
│                  │ localhost:8080                       │
│                  ▼                                      │
│         ┌────────────────┐                             │
│         │  CNKI API 服务   │  cnki_api.py (FastAPI)    │
│         │  /search        │  /paper   /pdf            │
│         └────────┬────────┘                             │
│                  │ localhost:3456                       │
│                  ▼                                      │
│         ┌────────────────┐                              │
│         │  CDP Proxy     │  cdp-proxy.mjs (Node.js)    │
│         │  HTTP → WS    │                             │
│         └────────┬────────┘                              │
│                  │ localhost:9222                       │
│                  ▼                                      │
│         ┌────────────────┐                              │
│         │ Chrome Debug   │  (已登录状态)                  │
│         │ kns.cnki.net  │                              │
│         └────────┬────────┘                              │
│                  │ 公开无需认证                          │
│                  ▼                                      │
│         ┌────────────────┐                              │
│         │ a.cnki.net     │  PDF 文件下载                 │
│         │ (PDF 公开)     │                              │
│         └────────────────┘                              │
└─────────────────────────────────────────────────────────┘
```

**三层技术栈：**
- **Chrome Debug**（必须）：维持登录态，渲染搜索结果和详情页
- **CDP Proxy**（Node.js）：HTTP ↔ WebSocket 协议转换
- **REST API / Python 脚本**（可选）：批量操作的编程接口

---

## 📡 REST API 端点

启动后访问 `http://localhost:8080/`

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查，返回 Chrome 标签页状态 |
| `GET` | `/targets` | 列出所有 Chrome 标签页 |
| `GET` | `/search?kw=关键词&pages=1` | 搜索 CNKI 论文 |
| `GET` | `/paper?url=详情页URL` | 提取单篇论文 PDF URL |
| `POST` | `/pdf` | 下载 PDF 到本地 |

**示例：**

```bash
# 健康检查
curl http://localhost:8080/health

# 搜索论文
curl "http://localhost:8080/search?kw=算电协同&pages=2"

# 提取PDF URL
curl "http://localhost:8080/paper?url=https://kns.cnki.net/kcms/detail/detail.aspx?dbcode=SCDB..."

# 下载PDF
curl -X POST "http://localhost:8080/pdf" \
  -d "pdf_url=https://a.cnki.net/gw/api/get/pdf/ads/v1/pdf/2025/11/xxxxx.pdf"
```

**返回格式示例（/search）：**

```json
{
  "keyword": "算电协同",
  "total": 40,
  "journal_count": 38,
  "newspaper_count": 2,
  "papers": [
    {
      "seq": "1",
      "title": "面向碳达峰碳中和的虚拟电厂市场化交易研究",
      "url": "https://kns.cnki.net/kcms/detail/detail.aspx?dbcode=SCDB...",
      "source": "中国电机工程学报",
      "date": "2025",
      "dbtype": "期刊"
    }
  ]
}
```

---

## 🤝 paper-ai 集成（中文AI学术写作）

本项目与 [paper-ai](https://github.com/chonpszhou/paper-ai) 深度集成：

```
paper-ai 论文来源选择:  [ arxiv | semantic scholar | pubmed | CNKI知网 ]
```

**集成效果：**
- ✅ 在 paper-ai 中直接搜索 CNKI 论文
- ✅ 自动提取论文元数据（标题/来源/年份）
- ✅ PDF 保存到 `~/Desktop/paper-ai/cnki_papers/`
- ✅ 引用插入 AI 写作内容，自动编号

**配置方法：**

```bash
# 1. 克隆 paper-ai
git clone https://github.com/chonpszhou/paper-ai.git
cd paper-ai && npm install

# 2. 启动 CNKI API 服务
cd ~/cnki-research-helper
./start.sh

# 3. 启动 paper-ai
npm run dev
```

**paper-ai 已包含的改动：**
- `components/GetCNKI.tsx` — CNKI 搜索组件
- `components/QuillEditor.tsx` — 新增 CNKI 数据源处理分支

---

## 📁 项目结构

```
cnki-research-helper/
├── README.md               # 本文件
├── LICENSE                 # MIT开源许可证
├── start.sh                # 一键启动脚本（Chrome + CDP Proxy + API）
├── scripts/
│   ├── cdp-proxy.mjs       # CDP代理（HTTP→WebSocket桥接）
│   ├── cnki_downloader.py  # 命令行下载工具
│   └── cnki_api.py         # REST API 服务（FastAPI）
└── docs/
    ├── setup-guide.md       # 详细配置指南
    └── workflow.md          # 技术原理详解
```

---

## ✨ 功能对比

| 功能 | 命令行下载 | REST API | paper-ai |
|------|-----------|----------|----------|
| 批量搜索 | ✅ | ✅ | ✅ |
| PDF下载 | ✅ | ✅ | ✅（本地） |
| AI写作引用 | ❌ | 需配合 | ✅ |
| 其他工具集成 | ❌ | ✅ | ❌ |

---

## 📊 实测效果

| 指标 | 数值 |
|------|------|
| 搜索"算电协同"总结果 | 112篇 |
| 期刊论文（有PDF） | 41篇 |
| 报纸文章（无PDF） | 70篇 |
| 单篇处理耗时 | ~6秒 |
| 100篇总耗时 | ~10分钟 |
| Cookie有效期 | ~30天 |
| PDF下载成功率 | **>90%**（排除报纸后） |
| API响应时间 | <500ms（不含CDP等待） |

---

## 🔬 技术原理

```
手动登录（触发滑动验证码）
    ↓ Chrome 已登录态
Python/Node.js 通过 CDP 控制 Chrome
    ↓
导航到搜索结果 → 提取论文URL列表（20篇/页）
    ↓
逐篇访问详情页 → 提取 a.cnki.net PDF URL
    ↓
curl 下载 PDF（无需认证，完全公开）
```

**关键发现**：知网的安全验证只保护「进入详情页」的过程，
一旦进入详情页，PDF链接就是普通公开链接，curl 直接下。

---

## ❓常见问题

**Q: 提示"找不到已登录CNKI的Chrome标签页"**
> 请确认 Chrome Debug 模式已启动，并且已打开并登录 https://login.cnki.net/

**Q: 下载PDF时大量失败**
> 重启服务：`./start.sh`

**Q: 报纸论文下载失败**
> 正常现象。知网报纸文章**不提供PDF**，只有CAJ格式（Mac不支持）。

**Q: paper-ai 显示"CNKI搜索失败"**
> 确保已运行 `./start.sh`，且 `curl http://localhost:8080/health` 返回正常。

**Q: API 端口被占用**
> `./start.sh --port 8081` 使用其他端口

**Q: Cookie多久过期？**
> 约30天。过期的Cookie需要重新登录 Chrome。

---

## ⚠️ 免责声明

- 本工具仅供**个人研究**使用，请遵守知网服务条款
- 批量下载请仅限于个人学习研究，**勿用于商业目的**
- 论文版权属于作者和期刊，知网仅提供分发服务
- 本工具不修改或破解知网任何安全机制

---

## 🙏 致谢

- [eze-is/web-access](https://github.com/eze-is/web-access) — CDP Proxy架构
- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/) — 浏览器自动化基础设施
- [paper-ai](https://github.com/14790897/paper-ai) — 学术写作AI工具
- 所有为爱发电的学术研究者

---

<div align="center">

**如果这个工具帮你省了时间和钱，请点个 ⭐**

</div>
