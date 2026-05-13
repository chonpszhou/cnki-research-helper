#!/usr/bin/env node
// CDP Proxy v3 - 修复版（Chrome page-level WS only）
// 架构：/json 获取页面列表，每个页面独立 WS 连接
import http from 'node:http';
import { URL } from 'node:url';
import { WebSocket } from 'ws';

const PORT = parseInt(process.argv[2] || process.env.CDP_PROXY_PORT || '3456');
const CHROME_PORT = parseInt(process.argv[3] || '9222');

// --- 获取所有 page targets（含真实 wsUrl）---
async function getPageTargets() {
  const resp = await fetch(`http://127.0.0.1:${CHROME_PORT}/json`);
  if (!resp.ok) throw new Error(`Chrome /json 返回 ${resp.status}`);
  const targets = await resp.json();
  return targets.filter(t => t.type === 'page');
}

// --- 为每个 page 建立独立的 CDP WS 连接 ---
const pageConnections = new Map(); // targetId -> { ws, cmdId:0, pending:Map }

function sendToPage(targetId, method, params = {}) {
  const conn = pageConnections.get(targetId);
  if (!conn || conn.ws.readyState !== WebSocket.OPEN) {
    throw new Error(`页面 ${targetId} 未连接`);
  }
  return new Promise((resolve, reject) => {
    const id = ++conn.cmdId;
    const msg = { id, method, params };
    const timer = setTimeout(() => {
      conn.pending.delete(id);
      reject(new Error(`CDP 超时: ${method}`));
    }, 30000);
    conn.pending.set(id, { resolve, reject, timer });
    conn.ws.send(JSON.stringify(msg));
  });
}

async function connectPage(target) {
  if (pageConnections.has(target.id)) {
    const existing = pageConnections.get(target.id);
    if (existing.ws.readyState === WebSocket.OPEN) return existing;
    existing.ws.close();
  }

  const wsUrl = target.webSocketDebuggerUrl;
  console.log(`[CDP] 连接页面 ${target.id}: ${wsUrl}`);

  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const conn = { ws, cmdId: 0, pending: new Map() };

    ws.on('open', () => {
      pageConnections.set(target.id, conn);
      console.log(`[CDP] 页面 ${target.id} 已连接`);
      resolve(conn);
    });

    ws.on('message', (data) => {
      const msg = JSON.parse(data.toString());
      // 事件消息（无 id）
      if (msg.id === undefined && msg.method) {
        // 忽略事件
        return;
      }
      // 响应消息
      if (msg.id && conn.pending.has(msg.id)) {
        const { resolve, reject, timer } = conn.pending.get(msg.id);
        clearTimeout(timer);
        conn.pending.delete(msg.id);
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg);
      }
    });

    ws.on('close', () => {
      console.log(`[CDP] 页面 ${target.id} 断开`);
      pageConnections.delete(target.id);
    });

    ws.on('error', (e) => {
      console.error(`[CDP] 页面 ${target.id} 错误:`, e.message);
      pageConnections.delete(target.id);
    });

    // 5秒超时
    setTimeout(() => {
      if (!pageConnections.has(target.id)) {
        ws.close();
        reject(new Error('连接超时'));
      }
    }, 5000);
  });
}

// --- HTTP API 服务器 ---
const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');

  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  try {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    const pathname = url.pathname;
    const q = Object.fromEntries(url.searchParams);

    // /health - 健康检查
    if (pathname === '/health') {
      const pages = await getPageTargets();
      res.end(JSON.stringify({
        status: 'ok',
        connectedPages: pageConnections.size,
        totalPages: pages.length,
        chromePort: CHROME_PORT,
      }));

    // /targets - 列出所有页面
    } else if (pathname === '/targets') {
      const pages = await getPageTargets();
      const result = pages.map(p => ({
        targetId: p.id,
        title: p.title,
        url: p.url,
        wsUrl: p.webSocketDebuggerUrl,
      }));
      res.end(JSON.stringify(result));

    // /connect?target=xxx - 主动连接某个页面
    } else if (pathname === '/connect') {
      const targetId = q.target;
      const pages = await getPageTargets();
      const target = pages.find(p => p.id === targetId);
      if (!target) { res.writeHead(404); res.end(JSON.stringify({ error: '页面未找到' })); return; }
      await connectPage(target);
      res.end(JSON.stringify({ ok: true, targetId }));

    // /info?target=xxx - 获取当前页面 URL
    } else if (pathname === '/info') {
      const targetId = q.target;
      if (!targetId) { res.writeHead(400); res.end(JSON.stringify({ error: '缺少 target' })); return; }
      try {
        const r = await sendToPage(targetId, 'Page.getNavigationHistory');
        const entries = r.result?.entries ?? [];
        const currentIndex = r.result?.currentIndex ?? 0;
        res.end(JSON.stringify({ targetId, url: entries[currentIndex]?.url ?? '' }));
      } catch (e) {
        // 如果页面没连接，先连接
        const pages = await getPageTargets();
        const target = pages.find(p => p.id === targetId);
        if (target) {
          await connectPage(target);
          const r2 = await sendToPage(targetId, 'Page.getNavigationHistory');
          const entries = r2.result?.entries ?? [];
          res.end(JSON.stringify({ targetId, url: entries[r2.result?.currentIndex ?? 0]?.url ?? '' }));
        } else {
          res.writeHead(404);
          res.end(JSON.stringify({ error: e.message }));
        }
      }

    // /navigate?target=xxx&url=xxx - 导航
    } else if (pathname === '/navigate') {
      const targetId = q.target;
      const targetUrl = q.url;
      if (!targetId || !targetUrl) { res.writeHead(400); res.end(JSON.stringify({ error: '缺少参数' })); return; }
      const pages = await getPageTargets();
      const target = pages.find(p => p.id === targetId);
      if (!target) { res.writeHead(404); res.end(JSON.stringify({ error: '页面未找到' })); return; }
      await connectPage(target);
      await sendToPage(targetId, 'Page.navigate', { url: targetUrl });
      res.end(JSON.stringify({ ok: true }));

    // /screenshot?target=xxx - 截图
    } else if (pathname === '/screenshot') {
      const targetId = q.target;
      if (!targetId) { res.writeHead(400); res.end(JSON.stringify({ error: '缺少 target' })); return; }
      const pages = await getPageTargets();
      const target = pages.find(p => p.id === targetId);
      if (!target) { res.writeHead(404); res.end(JSON.stringify({ error: '页面未找到' })); return; }
      await connectPage(target);
      const r = await sendToPage(targetId, 'Page.captureScreenshot', { format: 'png' });
      res.setHeader('Content-Type', 'image/png');
      res.end(Buffer.from(r.result.data, 'base64'));

    // /close?target=xxx - 关闭页面
    } else if (pathname === '/close') {
      const targetId = q.target;
      if (targetId && pageConnections.has(targetId)) {
        pageConnections.get(targetId).ws.close();
        pageConnections.delete(targetId);
      }
      res.end(JSON.stringify({ ok: true }));

    // /eval?target=xxx&script=xxx - 执行 JS 并返回结果
    } else if (pathname === '/eval') {
      const targetId = q.target;
      const script = q.script || '';
      if (!targetId) { res.writeHead(400); res.end(JSON.stringify({ error: '缺少 target' })); return; }
      const pages = await getPageTargets();
      const target = pages.find(p => p.id === targetId);
      if (!target) { res.writeHead(404); res.end(JSON.stringify({ error: '页面未找到' })); return; }
      await connectPage(target);
      const r = await sendToPage(targetId, 'Runtime.evaluate', {
        expression: script,
        returnByValue: true,
        awaitPromise: false,
      });
      const result = r.result?.result;
      if (result?.type === 'string') {
        res.end(JSON.stringify({ type: result.type, value: result.value }));
      } else {
        res.end(JSON.stringify({ type: result?.type, description: result?.description }));
      }

    } else {
      res.writeHead(404);
      res.end(JSON.stringify({ error: '未知端点', available: ['/health','/targets','/connect','/info','/navigate','/screenshot','/close'] }));
    }
  } catch (e) {
    console.error('[HTTP Error]', e.message);
    res.writeHead(500);
    res.end(JSON.stringify({ error: e.message }));
  }
});

server.listen(PORT, () => {
  console.log(`[CDP Proxy v3] http://127.0.0.1:${PORT}`);
  console.log(`  /health       - 健康检查`);
  console.log(`  /targets      - 列出所有页面（含 wsUrl）`);
  console.log(`  /connect?target=xxx - 主动连接页面`);
  console.log(`  /info?target=xxx - 当前 URL`);
  console.log(`  /navigate?target=xxx&url=xxx - 导航`);
  console.log(`  /screenshot?target=xxx - 截图`);
  console.log(`  /close?target=xxx - 关闭页面`);
});
