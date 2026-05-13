#!/usr/bin/env python3
"""
CNKI论文批量下载工具
CNKI Academic Paper Batch Download Tool

使用方法:
  1. 手动登录知网一次，导出Cookie（见 docs/setup-guide.md）
  2. 设置环境变量或修改下方配置
  3. 运行: python3 cnki_downloader.py --keyword "算电协同"

环境变量:
  CNKI_COOKIES   Cookie字符串（从浏览器导出）
  CNKI_PROXY     CDP Proxy地址（默认 http://127.0.0.1:3456）
  SAVE_DIR       PDF保存目录（默认 ./downloads）
"""

import subprocess
import json
import time
import os
import re
import argparse
from urllib.parse import quote

# ========== 配置（可改用环境变量）==========
CNKI_PROXY = os.environ.get("CNKI_PROXY", "http://127.0.0.1:3456")
SAVE_DIR    = os.environ.get("SAVE_DIR", "./downloads")
# ==========================================

TAB_ID = ""  # 运行时自动获取


def cdp_eval(js: str, tab: str = "", timeout: int = 15) -> str:
    """通过CDP Proxy执行JS，返回结果字符串"""
    if not tab:
        tab = TAB_ID
    r = subprocess.run(
        ["curl", "-G", f"{CNKI_PROXY}/eval",
         "--data-urlencode", f"target={tab}",
         "--data-urlencode", f"script={js}",
         "-s", "--max-time", str(timeout)],
        capture_output=True, text=True, timeout=timeout + 5
    )
    try:
        return json.loads(r.stdout).get("value", "")
    except Exception:
        return ""


def navigate(url: str, tab: str = "") -> bool:
    """导航Chrome到指定URL"""
    if not tab:
        tab = TAB_ID
    encoded = quote(url, safe="")
    r = subprocess.run(
        ["curl", "-s", f"{CNKI_PROXY}/navigate?target={tab}&url={encoded}"],
        capture_output=True, timeout=15
    )
    try:
        return json.loads(r.stdout.decode()).get("ok", False)
    except Exception:
        return False


def get_targets() -> list:
    """获取所有Chrome标签页"""
    r = subprocess.run(
        ["curl", "-s", f"{CNKI_PROXY}/targets"],
        capture_output=True, text=True, timeout=10
    )
    try:
        return json.loads(r.stdout)
    except Exception:
        return []


def get_logged_in_tab() -> str:
    """找到已登录CNKI的标签页"""
    targets = get_targets()
    for t in targets:
        if "cnki" in t.get("url", "").lower() or "中国知网" in t.get("title", ""):
            return t.get("targetId", "")
    return ""


def get_search_results(tab: str = "") -> list:
    """从搜索结果页提取所有论文URL"""
    if not tab:
        tab = TAB_ID

    js = r"""(function(){
  var t = document.querySelector('.result-table,#GridCpTable,.list-tab')
      || Array.from(document.querySelectorAll('table')).find(function(t){
        return t.textContent.includes('""" + os.environ.get("KEYWORD", "算电协同") + r"""')&&t.querySelector('a[href*=kcms2]');
      });
  if(!t) return JSON.stringify({error: 'no table', bodyLen: document.body.innerText.length});
  var rows = t.querySelectorAll('tr');
  var r = [];
  for(var row of rows){
    var cells = row.querySelectorAll('td');
    if(cells.length < 5) continue;
    var link = row.querySelector('a[href*=kcms2]');
    if(!link) continue;
    r.push({
      seq:    cells[0].textContent.trim(),
      title:  link.textContent.trim().slice(0, 80),
      url:    link.href,
      source: cells.length > 2 ? cells[2].textContent.trim().replace(/\s+/g,'') : '',
      date:   cells.length > 3 ? cells[3].textContent.trim() : '',
      dbtype: cells.length > 4 ? cells[4].textContent.trim() : ''
    });
  }
  return JSON.stringify(r);
})()"""

    result = cdp_eval(js, tab)
    try:
        data = json.loads(result)
        if isinstance(data, dict) and "error" in data:
            print(f"  ⚠️  {data['error']}, bodyLen={data.get('bodyLen','?')}")
            return []
        return json.loads(result)
    except Exception:
        return []


def extract_pdf_url(detail_url: str, tab: str = "") -> str:
    """
    访问论文详情页，提取PDF下载URL
    返回: PDF URL 或 None（无PDF/触发安全验证）
    """
    if not tab:
        tab = TAB_ID

    # 导航到详情页
    ok = navigate(detail_url, tab)
    if not ok:
        return None
    time.sleep(5)

    # 检测安全验证
    title = cdp_eval("document.title", tab)
    if "安全验证" in title or "verify" in title.lower():
        print(f"    ⚠️ 安全验证拦截")
        return None

    # 提取 a.cnki.net PDF URL
    js_escape = quote(
        r"""(function(){
  var html = document.body.innerHTML;
  var m = html.match(/a\.cnki\.net\/gw\/api\/get\/pdf\/[^\s"']+/g);
  var pdfs = (m||[]).filter(function(u){return u.toLowerCase().includes('.pdf');});
  if(pdfs.length > 0) return pdfs[0];
  return null;
})()"""
    )
    result = cdp_eval(js_escape[:200], tab)  # type: ignore

    # 如果上面的方式失败，尝试备选方法
    if not result or result == "null":
        js2 = r"""(function(){
  var btns = document.querySelectorAll('a[onclick*="pdf"],a[href*="a.cnki.net"]');
  for(var b of btns){
    var h = b.href || b.getAttribute('onclick') || '';
    if(h.includes('a.cnki.net') && h.includes('pdf')) return h.slice(0,150);
  }
  return null;
})()"""
        result = cdp_eval(js2, tab)

    if result and result != "null" and result.startswith("http"):
        return result
    return None


def download_pdf(pdf_url: str, save_path: str) -> bool:
    """
    用curl下载PDF（无需认证，a.cnki.net公开）
    """
    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    r = subprocess.run(
        ["curl", "-L", "-o", save_path, "-s", "--max-time", "30", "-A", ua, pdf_url],
        capture_output=True, timeout=35
    )
    if os.path.exists(save_path):
        size = os.path.getsize(save_path)
        if size > 5000:
            with open(save_path, "rb") as f:
                return f.read(5) == b"%PDF-"
    return False


def next_page(tab: str = "") -> bool:
    """点击下一页，返回是否成功"""
    if not tab:
        tab = TAB_ID

    js = r"""(function(){
  var pages = document.querySelectorAll('.pagesnums a,.pager a');
  for(var p of pages){
    if(p.textContent.trim().includes('\u4e0b\u4e00\u9875') || p.textContent.includes('>>')){
      p.dispatchEvent(new MouseEvent('click',{bubbles:true}));
      return true;
    }
  }
  return false;
})()"""
    result = cdp_eval(js, tab)
    time.sleep(3)
    return result == "true"


# ========== 主流程 ==========

def main():
    parser = argparse.ArgumentParser(description="CNKI论文批量下载工具")
    parser.add_argument("--keyword", "-k", default=os.environ.get("KEYWORD", "算电协同"),
                        help="搜索关键词（默认: 算电协同）")
    parser.add_argument("--pages", "-p", type=int, default=1,
                        help="抓取页数（默认: 1）")
    parser.add_argument("--type", "-t", default="all",
                        choices=["all", "journal", "newspaper"],
                        help="论文类型: all/journal/newspaper（默认: all）")
    parser.add_argument("--skip-pdf", action="store_true",
                        help="仅提取URL，不下载PDF")
    args = parser.parse_args()

    global TAB_ID
    TAB_ID = get_logged_in_tab()
    if not TAB_ID:
        print("❌ 找不到已登录CNKI的Chrome标签页")
        print("请先用Chrome登录 https://login.cnki.net/")
        return

    print(f"✅ 已找到CNKI标签页: {TAB_ID[:20]}...")
    print(f"搜索词: {args.keyword}")
    print(f"保存目录: {SAVE_DIR}")
    os.makedirs(SAVE_DIR, exist_ok=True)

    # 1. 导航到搜索结果
    search_url = f"https://kns.cnki.net/kns8s/defaultresult/index?kw={quote(args.keyword)}&korder=SC"
    print(f"\n--- 导航到搜索结果 ---")
    navigate(search_url, TAB_ID)
    time.sleep(6)

    all_papers = []
    for page in range(1, args.pages + 1):
        print(f"\n--- 第 {page}/{args.pages} 页 ---")
        papers = get_search_results(TAB_ID)
        if not papers:
            print("⚠️ 未提取到论文，可能需要增加等待时间")
            # 打印页面标题辅助诊断
            title = cdp_eval("document.title", TAB_ID)
            body_preview = cdp_eval("document.body.innerText.slice(0,200)", TAB_ID)
            print(f"  页面标题: {title}")
            print(f"  内容预览: {body_preview[:150]}")
            break

        # 按类型过滤
        if args.type == "journal":
            papers = [p for p in papers if "期刊" in p.get("dbtype", "")]
        elif args.type == "newspaper":
            papers = [p for p in papers if "报纸" in p.get("dbtype", "")]

        print(f"本页找到 {len(papers)} 篇论文（类型: {args.type}）")
        all_papers.extend(papers)

        if page < args.pages:
            if next_page(TAB_ID):
                time.sleep(5)
            else:
                print("已到最后一页")
                break

    print(f"\n共获取 {len(all_papers)} 篇论文")

    # 保存URL列表
    url_list_path = os.path.join(SAVE_DIR, f"urls_{int(time.time())}.json")
    with open(url_list_path, "w", encoding="utf-8") as f:
        json.dump(all_papers, f, ensure_ascii=False, indent=2)
    print(f"URL列表已保存: {url_list_path}")

    if args.skip_pdf:
        print("\n✅ 完成（skip-pdf模式）")
        return

    # 2. 逐篇提取PDF并下载
    print(f"\n--- 开始下载PDF ---")
    success = fail = skip = 0

    for i, paper in enumerate(all_papers, 1):
        db = paper.get("dbtype", "")
        safe_title = re.sub(r"[\\/:*?\"<>|]", "_", paper["title"])[:40]
        print(f"\n[{i}/{len(all_papers)}] {paper['title'][:45]} [{db}]")

        # 报纸通常无PDF
        if "报纸" in db:
            print(f"  ⏭ 报纸文章，无PDF，跳过")
            skip += 1
            continue

        pdf_url = extract_pdf_url(paper["url"], TAB_ID)
        if not pdf_url:
            fail += 1
            continue

        print(f"  📄 PDF: {pdf_url[:70]}...")
        save_path = os.path.join(SAVE_DIR, f"{safe_title}.pdf")
        ok = download_pdf(pdf_url, save_path)

        if ok:
            size = os.path.getsize(save_path)
            print(f"  ✅ 成功 ({size // 1024}KB) -> {os.path.basename(save_path)}")
            success += 1
        else:
            print(f"  ❌ 下载失败")
            fail += 1

        time.sleep(1.5)  # 避免请求过快

    # 3. 汇总
    print(f"\n{'='*50}")
    print(f"完成！成功 {success} | 失败 {fail} | 跳过 {skip} | 总计 {len(all_papers)}")
    print(f"保存目录: {SAVE_DIR}")


if __name__ == "__main__":
    main()
