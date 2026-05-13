<!-- CNKI研究助手 - 让人人都能批量下论文 -->

<div align="center">

# 🔓 CNKI研究助手

**知网论文 · 批量下载 · 自动笔记**

*「发现知网PDF竟然公开可下，激动得差点从椅子上摔下来」*

[![MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-green.svg)]()
[![Node.js](https://img.shields.io/badge/Node.js-16+-yellow.svg)]()

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

这个工具就是：**用Chrome替你过门卫 → 批量拿到PDF → 自动整理成笔记**

```
一次手动登录  →  批量下载100篇论文  →  自动生成Obsidian笔记
   3分钟              30分钟                 0分钟
```

---

## ⚡ 30秒上手

### 1. 启动专用Chrome（与日常浏览器隔离）

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome-Debug-CNKI" \
  --no-first-run --no-default-browser-check &
```

### 2. 启动代理（桥接Chrome和脚本）

```bash
cd ~/cnki-research-helper
node scripts/cdp-proxy.mjs 3456 9222 &
```

### 3. 手动登录知网（一次性）

在Chrome窗口里打开 → `https://login.cnki.net/` → 登录你的账号

### 4. 开始下载！

```bash
# 搜索"算电协同"，下载前2页
python3 scripts/cnki_downloader.py -k "算电协同" -p 2

# 速度：约5-8秒/篇（含导航+渲染等待）
```

**输出示例：**
```
✅ 已找到CNKI标签页: 732E907A2E167F5...
搜索词: 算电协同

--- 第 1/2 页 ---
本页找到 20 篇论文

[1/20] 面向碳达峰碳中和的虚拟电厂市场化交易研究 [期刊]
  📄 PDF: https://a.cnki.net/gw/api/get/pdf/ads/v1/pdf/2025/11/ead96fb...
  ✅ 成功 (358KB) -> 面向碳达峰碳中和的虚拟电厂.pdf

[2/20] 考虑碳排放的微电网调度研究 [期刊]
  📄 PDF: https://a.cnki.net/gw/api/get/pdf/ads/v1/pdf/2025/3/7fdc50f6...
  ✅ 成功 (412KB) -> 考虑碳排放的微电网调度研究.pdf

...

==================================================
完成！成功 37 | 失败 3 | 跳过 20 | 总计 60
保存目录: ./downloads
```

---

## ✨ 功能

| 功能 | 说明 |
|------|------|
| 🔍 批量搜索 | 按关键词搜索知网，指定页数 |
| 📄 PDF下载 | 识别有PDF的论文（期刊），跳过报纸（无PDF） |
| 🏷️ Obsidian笔记 | 自动生成Markdown笔记，带分类标签 |
| 🔒 隐私优先 | Cookie本地存储，不上传任何数据 |
| ⚙️ 通用设计 | 移除所有硬编码，任何知网账号都能用 |

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

---

## 🔬 技术原理（好奇心驱动）

```
你的电脑
  │
  │  ① 手动登录（触发滑动验证码，只能人来操作）
  │     Cookie 保存在 ~/.cnki_cookies.txt
  │
  ▼
Chrome Debug（你的登录状态）
  │
  │  ② Python脚本通过CDP协议控制Chrome
  │     → 导航到搜索结果（浏览器渲染出完整页面）
  │     → 点击进入论文详情页（绕过安全验证）
  │     → 从HTML提取PDF链接
  │
  ▼
 ③ a.cnki.net（PDF文件，公开无需认证）
  │  curl -L -o paper.pdf "https://a.cnki.net/..."
  │  ← 真正的PDF文件，大小通常200KB-2MB
  │
  ▼
本地 .pdf 文件
  │
  ▼
④ Obsidian笔记生成（可选）
```

**关键发现**：知网的安全验证只保护「进入详情页」的过程，
一旦进入详情页，PDF链接就是普通公开链接。

详见 [docs/workflow.md](docs/workflow.md)

---

## 📁 项目结构

```
cnki-research-helper/
├── README.md              # 本文件
├── LICENSE                # MIT开源许可证
├── scripts/
│   ├── cdp-proxy.mjs     # CDP代理（HTTP→WebSocket桥接）
│   └── cnki_downloader.py # 主下载脚本
└── docs/
    ├── setup-guide.md     # 详细配置指南
    └── workflow.md        # 技术原理详解
```

---

## ❓常见问题

**Q: 提示"找不到已登录CNKI的Chrome标签页"**
> Cookie过期了。重新登录知网，更新Cookie文件即可。

**Q: 下载PDF时大量失败**
> 重启CDP Proxy：`pkill -f cdp-proxy.mjs && node scripts/cdp-proxy.mjs 3456 9222 &`

**Q: 报纸论文下载失败**
> 正常现象。知网报纸文章**不提供PDF**，只有CAJ格式（需要Windows的CAJViewer）。

**Q: 机构账号登录不了**
> 如果你用VPN出口IP不在机构范围内，机构登录会被拒绝。此时用个人账号登录也可以下载（只是部分收费论文无权限）。

**Q: Cookie多久过期？**
> 约30天。过期的Cookie无法访问论文详情页，但不影响搜索结果页的元数据提取。

详见 [docs/setup-guide.md](docs/setup-guide.md)

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
- 所有为爱发电的学术研究者

---

<div align="center">

**如果这个工具帮你省了时间和钱，请点个 ⭐**

</div>
