# CNKI研究助手

> 用Chrome自动化批量下载知网论文PDF + 生成Obsidian笔记

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 功能

- 🔍 **批量搜索** — 按关键词搜索CNKI，指定页数
- 📄 **自动下载PDF** — 识别有PDF的论文（期刊），跳过报纸（无PDF）
- 🏷️ **生成Obsidian笔记** — 可选，自动按分类生成Markdown笔记
- 🔒 **隐私优先** — 不上传任何数据，Cookie本地存储，可完全离线使用
- ⚙️ **通用设计** — 移除所有硬编码账号，任何CNKI账号均可使用

## 效果

| 论文类型 | PDF可用 | 说明 |
|---------|--------|------|
| 期刊论文 | ✅ | 通常有PDF，可下载 |
| 报纸文章 | ❌ | 无PDF，仅CAJ格式 |
| 学位论文 | ⚠️ | 部分可下，需单独处理 |

## 快速开始

详细配置见 [docs/setup-guide.md](docs/setup-guide.md)

### 1. 启动Chrome Debug + CDP Proxy

```bash
# 终端1：启动专用Chrome
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome-Debug-CNKI" \
  --no-first-run --no-default-browser-check &

# 终端2：启动CDP Proxy
cd scripts
node cdp-proxy.mjs 3456 9222 &
```

### 2. 手动登录CNKI（一次性）

在Chrome中打开 `https://login.cnki.net/`，登录后导出Cookie到 `~/.cnki_cookies.txt`

### 3. 运行下载

```bash
export CNKI_COOKIES="$(cat ~/.cnki_cookies.txt)"

# 搜索"碳中和"，下载前2页
python3 scripts/cnki_downloader.py -k "碳中和" -p 2

# 仅期刊，仅1页
python3 scripts/cnki_downloader.py -k "储能" -t journal
```

## 工作原理

```
Chrome Debug（登录状态）
    │
    ▼ CDP Proxy（HTTP → WebSocket）
Python脚本
    │ 导航到论文详情页 → 从DOM提取PDF URL
    │
    ▼ 公开URL，无需认证
curl 下载 PDF 文件
```

核心发现：**知网PDF文件在 `a.cnki.net` 完全公开**，安全验证只保护"进入详情页"的过程。工具通过浏览器导航绕过验证，再用curl下载公开PDF。

详见 [docs/workflow.md](docs/workflow.md)

## 项目结构

```
cnki-research-helper/
├── README.md
├── LICENSE
├── .gitignore
├── scripts/
│   ├── cdp-proxy.mjs       # Chrome CDP Proxy（HTTP→WS桥接）
│   ├── cnki_downloader.py  # 主下载脚本
│   └── extract_notes.py    # Obsidian笔记生成（可选）
└── docs/
    ├── setup-guide.md      # 配置指南
    └── workflow.md         # 工作原理
```

## 环境要求

- macOS / Linux / Windows（需调整Chrome路径）
- Python 3.8+
- Node.js 16+（用于CDP Proxy）
- Google Chrome
- CNKI账号（机构或个人均可）

## 常见问题

**Q: 提示"找不到已登录CNKI的Chrome标签页"**
> 重新执行登录步骤，导出最新Cookie

**Q: 大量PDF下载失败**
> 重启CDP Proxy：`pkill -f cdp-proxy.mjs && node cdp-proxy.mjs 3456 9222 &`

**Q: 报纸论文下载失败**
> 正常现象，CNKI报纸文章不提供PDF

**Q: Cookie过期了**
> 重新手动登录CNKI，导出新Cookie覆盖 `~/.cnki_cookies.txt`

详见 [docs/setup-guide.md](docs/setup-guide.md#常见问题)

## 免责声明

本工具仅供个人研究使用。请遵守CNKI服务条款，尊重论文版权。批量下载仅适用于个人学习研究，请勿用于商业目的。
