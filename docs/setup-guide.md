# CNKI研究助手 - 环境配置指南

> 适用对象：任何拥有CNKI机构/个人账号的研究者
> 支持平台：macOS（Linux/Windows 类似）

---

## 前提条件

### 1. Chrome浏览器
系统已安装 Google Chrome（任何版本均可）

### 2. Node.js
```bash
node --version   # 需要 v16+
npm --version
```
如未安装: https://nodejs.org/

---

## 快速安装

```bash
# 克隆（或下载）本项目
git clone https://github.com/YOUR_USERNAME/cnki-research-helper.git
cd cnki-research-helper

# 安装依赖（仅Python标准库，无需pip install）
# 可选：确认curl可用
curl --version
```

---

## 第一步：启动Chrome Debug模式

**必须与日常使用的Chrome隔离**，否则会影响正常浏览。

```bash
# macOS 启动专用Debug Chrome
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome-Debug-CNKI" \
  --no-first-run \
  --no-default-browser-check &
```

> 提示：第一次运行后，`Chrome-Debug-CNKI` 配置文件夹会被创建，以后直接运行即可自动复用。

### 验证Chrome Debug是否启动
```bash
curl -s http://127.0.0.1:9222/json/version | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print('✅ Chrome:', d['Browser'])"
```
期望输出：`✅ Chrome: Chrome/xxx.x.xxxx.xx`

---

## 第二步：启动CDP Proxy

```bash
# 在项目目录下
cd cnki-research-helper/scripts

# 启动CDP Proxy（端口3456 → Chrome 9222）
node cdp-proxy.mjs 3456 9222 &
```

> `cdp-proxy.mjs` 已包含在本项目的 `scripts/` 目录下。

### 验证Proxy是否正常
```bash
curl -s http://127.0.0.1:3456/health
```
期望输出：`{"status":"ok","proxy":"cdp-proxy","version":"..."}`

---

## 第三步：手动登录CNKI（一次性操作）

CNKI有Tencent滑动验证码，**无法自动化登录**，需要手动操作一次。

### 3.1 打开登录页
在已启动的Debug Chrome中（你刚才启动的窗口）访问：
```
https://login.cnki.net/
```

### 3.2 登录
- 输入你的**知网账号**（机构账号或个人账号均可）
- 完成滑动验证
- 确认登录成功（显示机构名称或个人中心）

### 3.3 导出Cookie（重要！）
登录后，在Debug Chrome地址栏执行以下JavaScript：

1. 打开开发者工具：`Cmd + Option + J`（Mac）
2. 切换到 **Console（控制台）** 标签
3. 粘贴以下代码并回车：

```javascript
copy(document.cookie);
console.log("✅ Cookie已复制到剪贴板，长度:", document.cookie.length);
```

4. 将复制的内容保存到文件：
```bash
# 方式1：直接粘贴到文件
echo '刚才复制的cookie内容' > ~/.cnki_cookies.txt

# 方式2：用Python保存
python3 -c "
import subprocess
subprocess.run(['pbcopy'], input=input('粘贴Cookie后按Enter: ').encode())
" > ~/.cnki_cookies.txt
```

### 3.4 验证Cookie
```bash
wc -c ~/.cnki_cookies.txt
# 期望：> 100 字节（Cookie通常几百字节）
```

> ⚠️ **Cookie有效期**：机构账号约30天，个人账号更短。过期后重新执行3.1-3.4即可。

---

## 第四步：配置并运行下载工具

### 4.1 设置Cookie环境变量
```bash
export CNKI_COOKIES="$(cat ~/.cnki_cookies.txt)"
```

### 4.2 基本用法
```bash
cd ~/cnki-research-helper

# 搜索"算电协同"，下载前2页
python3 scripts/cnki_downloader.py -k "算电协同" -p 2

# 仅下载期刊论文
python3 scripts/cnki_downloader.py -k "碳资产管理" -t journal

# 仅提取URL，不下载PDF（快速测试）
python3 scripts/cnki_downloader.py -k "储能" --skip-pdf
```

### 4.3 完整参数
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-k, --keyword` | 搜索关键词 | 环境变量`KEYWORD`或"算电协同" |
| `-p, --pages` | 抓取页数 | 1 |
| `-t, --type` | 论文类型：`all/journal/newspaper` | all |
| `--skip-pdf` | 仅提取URL，不下载PDF | false |

### 4.4 自定义保存目录
```bash
export SAVE_DIR="/Users/yourname/Papers"
python3 scripts/cnki_downloader.py -k "你的关键词"
```

---

## 常见问题

### Q1: 提示"找不到已登录CNKI的Chrome标签页"
**原因**：Debug Chrome未启动，或Cookie已过期。
```bash
# 检查Chrome Debug状态
curl -s http://127.0.0.1:9222/json | python3 -c \
  "import sys,json; tabs=json.load(sys.stdin); print('标签页数:', len([t for t in tabs if t['type']=='page']))"
```
**解决**：重新启动Chrome Debug，并重新登录CNKI导出Cookie。

### Q2: 下载PDF时大量失败
**原因**：CDP Proxy连接不稳定，或网络问题。
**解决**：重启CDP Proxy（`pkill -f cdp-proxy.mjs && node cdp-proxy.mjs 3456 9222 &`）

### Q3: 报纸论文PDF下载失败
**正常现象**：CNKI报纸文章**不提供PDF**，仅有CAJ格式（需要Windows CAJViewer）。

### Q4: "安全验证"拦截
**原因**：CNKI风控触发。
**解决**：等待10分钟后再试，或隔天再试。建议避免短时间内大量请求。

### Q5: v=参数是什么？
知网详情页URL中的`v=`参数是**短期签名**，用于标识这篇论文的访问权限。同一URL反复访问会被拦截。工具会自动处理，每次从搜索结果重新获取最新URL。

---

## 项目结构

```
cnki-research-helper/
├── README.md              # 本文件
├── LICENSE                # MIT开源许可证
├── scripts/
│   ├── cdp-proxy.mjs      # CDP Proxy（Chrome DevTools协议桥接）
│   ├── cnki_downloader.py # 主下载脚本
│   └── extract_notes.py   # Obsidian笔记生成（可选）
└── docs/
    ├── setup-guide.md      # 本配置指南
    └── workflow.md         # 完整工作流程详解
```

---

## 卸载/清理

```bash
# 停止后台进程
pkill -f "cdp-proxy.mjs"

# 删除Debug Chrome配置（可选）
rm -rf "$HOME/Library/Application Support/Google/Chrome-Debug-CNKI"

# 删除Cookie
rm ~/.cnki_cookies.txt
```
