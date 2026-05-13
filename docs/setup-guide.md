# CNKI研究助手 · 配置指南

> 零基础图文教程，跟着做一定能成功

---

## 环境要求

| 软件 | 版本 | 说明 |
|------|------|------|
| macOS | 12+ | Windows/Linux类似 |
| Google Chrome | 任意版本 | [下载地址](https://www.google.com/chrome/) |
| Python | 3.8+ | `python3 --version` 检查 |
| Node.js | 16+ | `node --version` 检查，[下载地址](https://nodejs.org/) |

---

## 第一步：克隆项目

```bash
git clone https://github.com/chonpszhou/cnki-research-helper.git
cd cnki-research-helper
```

或者直接下载ZIP包，解压后进入目录。

---

## 第二步：启动Chrome Debug模式

> ⚠️ **必须使用独立Chrome配置**，否则会影响你正常使用的Chrome

### macOS

打开**终端**（Terminal），粘贴运行：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome-Debug-CNKI" \
  --no-first-run \
  --no-default-browser-check &
```

### Windows

```powershell
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="%USERPROFILE%\Chrome-Debug-CNKI" ^
  --no-first-run
```

### Linux

```bash
google-chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Chrome-Debug-CNKI" \
  --no-first-run &
```

> 💡 **第一次运行会创建配置文件夹**，以后直接运行上述命令即可，会自动复用。

### 验证Chrome启动成功

```bash
curl -s http://127.0.0.1:9222/json/version | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print('✅ Chrome已就绪:', d['Browser'])"
```

期望输出：`✅ Chrome已就绪: Chrome/148.x.xxxx.xx`

---

## 第三步：启动CDP Proxy

```bash
cd ~/cnki-research-helper/scripts
node cdp-proxy.mjs 3456 9222 &
```

### 验证Proxy启动成功

```bash
curl -s http://127.0.0.1:3456/health
```

期望输出：`{"status":"ok","proxy":"cdp-proxy",...}`

> 如果报错 `Connection refused`，等2秒再试（Chrome启动较慢）

---

## 第四步：手动登录知网

这是整个流程中**唯一需要人工操作**的步骤。

### 4.1 打开登录页

在刚才启动的Chrome窗口中，访问：
```
https://login.cnki.net/
```

### 4.2 完成登录

- 输入你的**知网账号**（机构账号或个人账号都行）
- 完成滑动验证码（人才能操作，程序做不到 😅）
- 确认登录成功（右上角显示你的名字/机构名）

### 4.3 导出Cookie

登录成功后，在Chrome地址栏：

1. 按 `Cmd + Option + J`（Mac）或 `F12`（Windows）打开开发者工具
2. 切换到 **Console（控制台）** 标签
3. 粘贴以下代码并回车：

```javascript
copy(document.cookie);
console.log("✅ Cookie已复制，长度:", document.cookie.length, "字节");
```

4. 你会看到 `✅ Cookie已复制，长度: 435 字节`（具体数字不重要，>100就对了）

### 4.4 保存Cookie到文件

回到终端，运行：

```bash
echo '请在这里粘贴刚才复制的Cookie内容（Cmd+V），然后按回车：' && \
read -r cookie && echo "$cookie" > ~/.cnki_cookies.txt && \
echo "✅ 已保存，$(wc -c < ~/.cnki_cookies.txt) 字节"
```

### 4.5 验证Cookie

```bash
wc -c ~/.cnki_cookies.txt
# 期望：> 100 字节
```

> ⚠️ **Cookie有效期约30天**。过期后重新执行4.1-4.4即可。

---

## 第五步：运行下载工具

### 基本用法

```bash
cd ~/cnki-research-helper

# 搜索"碳中和"，下载前2页
python3 scripts/cnki_downloader.py -k "碳中和" -p 2

# 仅下载期刊论文（跳过报纸）
python3 scripts/cnki_downloader.py -k "储能" -t journal

# 仅提取URL，不下载（快速测试）
python3 scripts/cnki_downloader.py -k "虚拟电厂" --skip-pdf
```

### 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `-k` | 搜索关键词 | `-k "算电协同"` |
| `-p` | 下载页数（每页20篇） | `-p 3`（下载60篇） |
| `-t` | 论文类型 | `-t journal`（仅期刊） |
| `--skip-pdf` | 只提取URL，不下PDF | 快速测试用 |

### 论文类型说明

| 类型 | 标记 | PDF可用 | 说明 |
|------|------|--------|------|
| 期刊论文 | 期刊 | ✅ 有 | 通常有PDF，可下载 |
| 报纸文章 | 报纸 | ❌ 无 | 只有CAJ格式 |
| 学位论文 | 硕士/博士 | ⚠️ 部分 | 通常可下 |

---

## 第六步：查看结果

```bash
# 查看下载的PDF
ls -lh ~/cnki-research-helper/downloads/

# 查看提取的URL列表
ls ~/cnki-research-helper/downloads/urls_*.json
```

---

## 常见问题排查

### 问题1：Chrome Debug连不上

```
curl: (7) Failed to connect to 127.0.0.1 port 9222
```

**原因**：Chrome Debug没启动成功
**解决**：重新运行Chrome启动命令，等待3秒后再试

### 问题2：Proxy连接被拒绝

```
Connection refused
```

**原因**：CDP Proxy没启动，或端口被占用
**解决**：
```bash
pkill -f cdp-proxy.mjs
node ~/cnki-research-helper/scripts/cdp-proxy.mjs 3456 9222 &
```

### 问题3：找不到已登录的标签页

```
❌ 找不到已登录CNKI的Chrome标签页
```

**原因**：Cookie已过期，或Chrome窗口没有打开知网
**解决**：
1. 重新登录知网（第四步）
2. 确认Chrome窗口开着知网页面（任意页面都行）

### 问题4：PDF下载全是错误页

```
❌ 下载失败（可能是错误页面）
```

**原因**：PDF URL过期（知网v=参数短期有效）
**解决**：这是正常现象，重试几次会好。或等待10分钟后再试（知网风控限制）

### 问题5：脚本运行很慢

**原因**：每次访问详情页要等待5秒让页面渲染
**解决**：这是设计如此，避免请求过快触发风控。耐心等待

---

## 一键启动脚本

嫌每次输命令麻烦？把这个保存为 `start.sh`：

```bash
#!/bin/bash
# 启动CNKI研究助手

echo "🚀 启动Chrome Debug..."
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome-Debug-CNKI" \
  --no-first-run --no-default-browser-check &

sleep 3

echo "🚀 启动CDP Proxy..."
cd ~/cnki-research-helper/scripts
node cdp-proxy.mjs 3456 9222 &

sleep 2
echo "✅ 就绪！请在Chrome中登录知网，然后运行下载脚本"
```

```bash
chmod +x start.sh
./start.sh
```

---

## 进阶用法

### 集成Obsidian笔记

```bash
# 下载完成后，用 Obsidian 插件「Metadata Menu」或「Frontmatter」自动读取PDF元数据
# 或使用 python-docx 将PDF路径写入笔记模板

# 示例：生成带PDF路径的Obsidian笔记
python3 -c "
import json, os
for f in os.listdir('downloads'):
    if f.endswith('.pdf'):
        name = f.replace('.pdf','')
        print(f'---\\ntitle: {name}\\npdf: ./downloads/{f}\\n---')
"
```

### 自定义搜索

```bash
# 多关键词搜索（分别运行）
python3 scripts/cnki_downloader.py -k "碳达峰 碳中和" -p 2
python3 scripts/cnki_downloader.py -k "储能 调度" -p 2
python3 scripts/cnki_downloader.py -k "源网荷储" -p 2
```

### 定时任务

```bash
# 每周一自动更新"碳中和"相关论文
# 添加到 crontab: crontab -e
0 9 * * 1 cd ~/cnki-research-helper && python3 scripts/cnki_downloader.py -k "碳中和" -p 1 >> logs/weekly.log 2>&1
```

---

*遇到问题？欢迎提交 [Issue](https://github.com/chonpszhou/cnki-research-helper/issues)*
