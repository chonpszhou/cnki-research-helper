#!/usr/bin/env python3
"""
CNKI REST API 服务
将 cnki_downloader 的 CDP 能力封装为 HTTP API，供 paper-ai 等前端调用。

启动方式:
    python3 cnki_api.py [--port 8080]

API 端点:
    GET  /health              健康检查
    GET  /search?kw=关键词&pages=1   搜索论文
    GET  /paper?url=详情页URL        提取PDF URL
    POST /pdf                  下载PDF到本地
    GET  /targets              列出所有Chrome标签页
"""

import subprocess
import json
import time
import os
import re
import argparse
import hashlib
import threading
from urllib.parse import quote, urlencode
from pathlib import Path
from typing import Optional

# ─── 导入 FastAPI ───────────────────────────────────────────────
try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    print("❌ 需要安装 fastapi 和 uvicorn: pip install fastapi uvicorn")
    exit(1)

# ─── 配置 ──────────────────────────────────────────────────────
CNKI_PROXY   = os.environ.get("CNKI_PROXY",   "http://127.0.0.1:3456")
SAVE_DIR      = os.environ.get("CNKI_PDF_DIR",
                   str(Path.home() / "Desktop" / "paper-ai" / "cnki_papers"))
os.makedirs(SAVE_DIR, exist_ok=True)

TAB_ID: Optional[str] = None
_tab_lock = threading.Lock()

# ─── CDP 底层 ─────────────────────────────────────────────────

def _curl(url: str, timeout: int = 15) -> str:
    r = subprocess.run(
        ["curl", "-s", "--max-time", str(timeout), url],
        capture_output=True, text=True, timeout=timeout + 5
    )
    return r.stdout


def _curl_post(url: str, data: dict, timeout: int = 15) -> str:
    encoded = urlencode(data)
    r = subprocess.run(
        ["curl", "-s", "--max-time", str(timeout),
         "-G", url, "--data-urlencode", encoded],
        capture_output=True, text=True, timeout=timeout + 5
    )
    return r.stdout


def cdp_eval(js: str, tab: str = "", timeout: int = 20) -> str:
    if not tab:
        tab = _get_tab()
    if not tab:
        return "{}"
    encoded_js = quote(js, safe="")
    r = _curl(
        f"{CNKI_PROXY}/eval?target={tab}&script={encoded_js}",
        timeout=timeout
    )
    try:
        return json.loads(r).get("value", "")
    except Exception:
        return ""


def cdp_navigate(url: str, tab: str = "") -> bool:
    if not tab:
        tab = _get_tab()
    if not tab:
        return False
    r = _curl(f"{CNKI_PROXY}/navigate?target={tab}&url={quote(url)}", timeout=15)
    try:
        return json.loads(r).get("ok", False)
    except Exception:
        return False


def cdp_targets() -> list:
    r = _curl(f"{CNKI_PROXY}/targets")
    try:
        return json.loads(r)
    except Exception:
        return []


def _get_tab() -> Optional[str]:
    global TAB_ID
    if TAB_ID:
        return TAB_ID
    targets = cdp_targets()
    for t in targets:
        # CDP Proxy 有时返回字符串而非字典，加此防御
        if isinstance(t, str):
            continue
        url = t.get("url", "").lower()
        title = t.get("title", "")
        if "cnki" in url or "中国知网" in title:
            with _tab_lock:
                TAB_ID = t.get("targetId", "")
            return TAB_ID
    return None


# ─── 核心业务 ─────────────────────────────────────────────────

def search_papers(keyword: str, pages: int = 1) -> dict:
    """
    搜索 CNKI，返回论文列表（不含 PDF URL）。
    支持 kns.cnki.net（旧版）和 www.cnki.net（新版，绕过 SSL）两种入口。
    返回: { total, papers: [{seq, title, url, source, date, dbtype}], warnings }
    """
    tab = _get_tab()
    if not tab:
        raise HTTPException(status_code=503, detail="未找到已登录CNKI的Chrome标签页，请先在Chrome中登录 https://login.cnki.net/")

    search_url = (
        f"https://kns.cnki.net/kns8s/defaultresult/index"
        f"?kw={quote(keyword)}&korder=SC"
    )

    cdp_navigate(search_url, tab)
    time.sleep(12)  # 新版结果动态加载，等待更久

    all_papers = []
    warnings = []

    for page in range(1, pages + 1):
        if page > 1:
            js = r"""(function(){
  var ps = document.querySelectorAll('.pagesnums a,.pager a');
  for(var p of ps){
    if(p.textContent.trim().includes('\u4e0b\u4e00\u9875')||p.textContent.includes('>>')){
      p.dispatchEvent(new MouseEvent('click',{bubbles:true})); return true;
    }
  }
  return false;
})()"""
            cdp_eval(js, tab)
            time.sleep(10)

        # 方案1：尝试 innerText 解析（兼容新版动态页面）
        papers = _extract_papers_by_text(tab, keyword)
        if papers:
            all_papers.extend(papers)
            warnings.append(f"第{page}页: innerText解析法成功({len(papers)}篇)")
        else:
            warnings.append(f"第{page}页: innerText解析法失败，尝试DOM解析")
            # 方案2：表格DOM解析（备用）
            papers_dom = _extract_papers_by_dom(tab, keyword)
            if papers_dom:
                all_papers.extend(papers_dom)
                warnings.append(f"第{page}页: DOM解析成功({len(papers_dom)}篇)")

    journal_count = sum(1 for p in all_papers if "期刊" in p.get("dbtype",""))
    newspaper_count = sum(1 for p in all_papers if "报纸" in p.get("dbtype",""))

    return {
        "keyword": keyword,
        "total": len(all_papers),
        "journal_count": journal_count,
        "newspaper_count": newspaper_count,
        "papers": all_papers,
        "warnings": warnings
    }


def _extract_papers_by_text(tab: str, keyword: str) -> list:
    """
    通过 innerText 提取论文列表（兼容新版动态渲染页面）。
    工作原理：搜索结果在页面加载完成后，innerText 中包含完整的题名列表。
    """
    js = r"""(function(){
  var text = (document.body ? document.body.innerText : '') || '';
  // 找到 "共找到 N 条结果" 之后的区域
  var resultsIdx = text.indexOf('共找到');
  if(resultsIdx < 0) return JSON.stringify({error: 'no results marker'});
  var section = text.slice(resultsIdx, resultsIdx + 8000);

  // 按换行分割，每行是一条结果信息
  var lines = section.split('\n').map(function(l){ return l.trim(); }).filter(function(l){ return l.length > 0; });

  var papers = [];
  var i = 0;
  while(i < lines.length) {
    var line = lines[i];
    // 找题名行：包含 kcms2 链接特征（题名后面通常跟着作者、期刊、年份）
    if(line.length > 10 && line.length < 200 && i + 2 < lines.length) {
      var nextLine = lines[i+1] || '';
      var next2Line = lines[i+2] || '';
      // 题名行特征：不包含 @qq 等邮箱后缀，不纯是数字，有一定长度
      if(!line.match(/^\d+$/) && !line.match(/@/) && line.length > 15 &&
         (nextLine.length < 30 || next2Line.length < 30)) {
        // 过滤掉分页导航、栏目名称
        if(!line.match(/上一页|下一页|首页|尾页|共找到|条结果/) &&
           !line.match(/^\d+$/) &&
           line.length < 150) {
          // 尝试从上下文推断作者、来源、年份
          var author = '';
          var source = '';
          var year = '';
          var date = '';
          for(var j = i+1; j < Math.min(i+6, lines.length); j++) {
            var ctx = lines[j] || '';
            // 年份 4位数字
            var ym = ctx.match(/(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{4}[-/]\d{1,2}|\d{4}年)/);
            if(ym && !year) year = ym[0];
            // 期刊/报纸名称（常见后缀）
            if((ctx.includes('学报') || ctx.includes('研究') || ctx.includes('评论') ||
                ctx.includes('民族') || ctx.includes('人民') || ctx.includes('中国') ||
                ctx.includes('学院') || ctx.includes('宗教') || ctx.includes('教育') ||
                ctx.includes('论坛') || ctx.includes('日报') || ctx.includes('期刊')) &&
               ctx.length < 40 && !ctx.match(/^\d+$/) && ctx.length > 4) {
              if(!source) source = ctx;
            }
            // 作者（常见格式：2-4个汉字）
            if(ctx.length > 0 && ctx.length < 15 && ctx.match(/^[\u4e00-\u9fa5]{2,6}$/) &&
               !ctx.includes('年') && !ctx.includes('月')) {
              if(!author) author = ctx;
            }
          }
          papers.push({
            title: line,
            url: '',
            author: author,
            source: source,
            year: year,
            dbtype: ''
          });
          i += 2; // 跳过题名和作者行
          continue;
        }
      }
    }
    i++;
  }
  // 去重
  var seen = {};
  papers = papers.filter(function(p){
    if(seen[p.title]) return false;
    seen[p.title] = true;
    return p.title.length > 15;
  });
  return JSON.stringify(papers.slice(0, 30));
})()"""
    result = cdp_eval(js, tab, timeout=25)
    try:
        data = json.loads(result)
        if isinstance(data, dict) and "error" in data:
            return []
        if isinstance(data, list) and len(data) > 0:
            return data
    except Exception:
        pass
    return []


def _extract_papers_by_dom(tab: str, keyword: str) -> list:
    """备用：通过 DOM 表格提取论文列表（兼容旧版页面）"""
    js = r"""(function(){
  var t = document.querySelector('.result-table,#GridCpTable,.list-tab')
      || Array.from(document.querySelectorAll('table')).find(function(t){
        return t.textContent.includes('""" + keyword + r"""')&&t.querySelector('a[href*=kcms2]');
      });
  if(!t) return JSON.stringify({error:'no table',len:document.body.innerText.length});
  var rows = t.querySelectorAll('tr');
  var r=[];
  for(var row of rows){
    var cells = row.querySelectorAll('td');
    if(cells.length<5) continue;
    var link = row.querySelector('a[href*=kcms2]');
    if(!link) continue;
    r.push({
      seq:    cells[0]?.textContent?.trim()||'',
      title:  link.textContent.trim().slice(0,80),
      url:    link.href,
      source: cells.length>2?cells[2].textContent.trim().replace(/\s+/g,''):'',
      date:   cells.length>3?cells[3].textContent.trim():'',
      dbtype: cells.length>4?cells[4].textContent.trim():''
    });
  }
  return JSON.stringify(r);
})()"""
    result = cdp_eval(js, tab)
    try:
        papers = json.loads(result)
        if isinstance(papers, dict) and "error" in papers:
            return []
        if isinstance(papers, list) and len(papers) > 0:
            return papers
    except Exception:
        pass
    return []


def extract_paper_pdf_url(detail_url: str) -> dict:
    """
    访问论文详情页，提取 PDF 下载 URL。
    返回: { pdf_url, title, source, is_journal }
    """
    tab = _get_tab()
    if not tab:
        raise HTTPException(status_code=503, detail="未找到CNKI标签页")

    cdp_navigate(detail_url, tab)
    time.sleep(5)

    # 检测安全验证
    title = cdp_eval("document.title", tab)
    if "安全验证" in title or "verify" in title.lower():
        raise HTTPException(status_code=429, detail="触发安全验证，请稍后重试")

    # 提取 PDF URL
    js1 = r"""(function(){
  var html=document.body.innerHTML;
  var m=html.match(/a\.cnki\.net\/gw\/api\/get\/pdf\/[^\s"']+/g);
  var pdfs=(m||[]).filter(function(u){return u.toLowerCase().includes('.pdf');});
  if(pdfs.length>0) return pdfs[0];
  return null;
})()"""
    result = cdp_eval(js1, tab)

    if not result or result == "null":
        js2 = r"""(function(){
  var btns=document.querySelectorAll('a[onclick*="pdf"],a[href*="a.cnki.net"]');
  for(var b of btns){
    var h=b.href||b.getAttribute('onclick')||'';
    if(h.includes('a.cnki.net')&&h.includes('pdf')) return h.slice(0,150);
  }
  return null;
})()"""
        result = cdp_eval(js2, tab)

    # 提取标题
    title_js = r"""(function(){
  var h=document.querySelector('h3.title')||document.querySelector('.title')||document.querySelector('h1');
  return h?h.textContent.trim().slice(0,80):'';
})()"""
    extracted_title = cdp_eval(title_js, tab)

    # 来源
    source_js = r"""(function(){
  var s=document.querySelector('.source')||document.querySelector('.journal')||document.querySelector('[class*="source"]');
  return s?s.textContent.trim():'';
})()"""
    extracted_source = cdp_eval(source_js, tab)

    is_journal = "期刊" in (extracted_source or "")

    if result and result.startswith("http"):
        return {
            "pdf_url": result,
            "title": extracted_title or detail_url,
            "source": extracted_source or "",
            "is_journal": is_journal
        }
    else:
        return {
            "pdf_url": None,
            "title": extracted_title or "",
            "source": extracted_source or "",
            "is_journal": is_journal,
            "note": "非期刊文章或无PDF（报纸只有CAJ格式）"
        }


def download_pdf(pdf_url: str, filename: str = "") -> dict:
    """
    下载 PDF 到 SAVE_DIR，返回本地路径、大小。
    """
    if not filename:
        # 用 URL hash 命名避免中文编码问题
        h = hashlib.md5(pdf_url.encode()).hexdigest()[:12]
        filename = f"{h}.pdf"

    save_path = os.path.join(SAVE_DIR, filename)
    os.makedirs(SAVE_DIR, exist_ok=True)

    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    r = subprocess.run(
        ["curl", "-L", "-o", save_path, "-s", "--max-time", "30", "-A", ua, pdf_url],
        capture_output=True, timeout=35
    )

    if os.path.exists(save_path):
        size = os.path.getsize(save_path)
        if size > 5000:
            with open(save_path, "rb") as f:
                if f.read(5) == b"%PDF-":
                    return {
                        "local_path": save_path,
                        "filename": filename,
                        "size_kb": size // 1024,
                        "status": "success"
                    }

    # 下载失败，清理
    if os.path.exists(save_path):
        os.remove(save_path)
    raise HTTPException(status_code=502, detail="PDF下载失败或文件无效")


# ─── FastAPI 应用 ─────────────────────────────────────────────

app = FastAPI(
    title="CNKI Research API",
    description="CNKI论文搜索与PDF下载REST API（供paper-ai等前端调用）",
    version="1.0.0"
)

# CORS：允许 localhost 开发 + Vercel 预览
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本地开发无限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """健康检查 + Chrome标签页状态"""
    tab = _get_tab()
    targets = cdp_targets()
    cnki_tabs = [t for t in targets if isinstance(t, dict) and "cnki" in t.get("url","").lower()]
    return {
        "status": "ok",
        "has_tab": bool(tab),
        "tab_id": tab[:16] + "..." if tab else None,
        "cnki_tabs": len(cnki_tabs),
        "pdf_dir": SAVE_DIR,
        "proxy": CNKI_PROXY
    }


@app.get("/targets")
def list_targets():
    """列出所有Chrome标签页"""
    return cdp_targets()


@app.post("/init-tab")
def init_tab():
    """手动指定/刷新 CNKI 标签页 ID"""
    global TAB_ID
    tab = _get_tab()
    if not tab:
        raise HTTPException(status_code=404, detail="未找到CNKI标签页，请确认Chrome已打开知网页面")
    return {"tab_id": tab, "note": "已缓存，后续请求自动使用"}


@app.get("/search")
def api_search(
    kw: str = Query(..., description="搜索关键词"),
    pages: int = Query(1, ge=1, le=10, description="抓取页数")
):
    """搜索 CNKI 论文"""
    return search_papers(kw, pages)


@app.get("/paper")
def api_paper(url: str = Query(..., description="论文详情页URL")):
    """提取单篇论文的PDF URL"""
    return extract_paper_pdf_url(url)


@app.post("/pdf")
def api_pdf(pdf_url: str, filename: str = ""):
    """下载PDF到本地"""
    return download_pdf(pdf_url, filename)


# ─── 启动 ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CNKI REST API 服务")
    parser.add_argument("--port", "-p", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════╗
║     CNKI Research API  (paper-ai 后端)        ║
╠══════════════════════════════════════════════╣
║  API:    http://{args.host}:{args.port}                ║
║  依赖:   CDP Proxy @ {CNKI_PROXY}      ║
║  PDF目录: {SAVE_DIR}  ║
╚══════════════════════════════════════════════╝
""")

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
