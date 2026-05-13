from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import Page, sync_playwright


DEFAULT_PORT = 9222
DEFAULT_PROFILE = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "browser-profiles" / "default"


def find_free_port(start: int = DEFAULT_PORT, limit: int = 50) -> int:
    for port in range(start, start + limit):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"no free port in range {start}..{start + limit - 1}")


def cdp_json(port: int, path: str = "/json/list") -> Any:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_tabs(port: int) -> List[Dict[str, Any]]:
    tabs = cdp_json(port, "/json/list")
    return [
        {
            "index": i,
            "id": tab.get("id", ""),
            "type": tab.get("type", ""),
            "title": tab.get("title", ""),
            "url": tab.get("url", ""),
            "webSocketDebuggerUrl": tab.get("webSocketDebuggerUrl", ""),
        }
        for i, tab in enumerate(tabs)
        if tab.get("type") == "page"
    ]


def connect_page(port: int, tab_index: Optional[int] = None, url_contains: str = "", title_contains: str = ""):
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=10000)
    pages: List[Page] = []
    for context in browser.contexts:
        pages.extend(context.pages)
    if not pages:
        browser.close()
        p.stop()
        raise RuntimeError("no pages available")

    page: Optional[Page] = None
    if tab_index is not None:
        if tab_index < 0 or tab_index >= len(pages):
            browser.close()
            p.stop()
            raise RuntimeError(f"tab_index out of range: {tab_index}, pages={len(pages)}")
        page = pages[tab_index]
    else:
        for candidate in pages:
            if url_contains and url_contains not in candidate.url:
                continue
            try:
                title = candidate.title()
            except Exception:
                title = ""
            if title_contains and title_contains not in title:
                continue
            page = candidate
            break
        if page is None:
            page = pages[-1]
    return p, browser, page, pages


def wait_soft(page: Page, timeout_ms: int = 10000) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=min(timeout_ms, 10000))
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        pass
    time.sleep(0.3)


def write_json(path: str | Path, data: Any) -> None:
    out = Path(path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def emit(data: Any, out: str = "") -> int:
    if out:
        write_json(out, data)
        print(str(Path(out).resolve()))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def fail(message: str, out: str = "") -> int:
    data = {"ok": False, "error": message}
    return emit(data, out)


SNAPSHOT_JS = r"""
() => {
  const SKIP_TAGS = new Set(['SCRIPT','STYLE','NOSCRIPT','TEMPLATE','META','LINK']);
  const BAD_TEXT = new Set(['']);
  const MAX_TEXT = 240;
  const rectOf = (el) => {
    const r = el.getBoundingClientRect();
    return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)};
  };
  const visible = (el) => {
    if (!el || SKIP_TAGS.has(el.tagName)) return false;
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity || 1) === 0) return false;
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    return true;
  };
  const clean = (s) => String(s || '').replace(/\s+/g, ' ').trim();
  const elementText = (el) => {
    const direct = clean(el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('placeholder'));
    if (direct) return direct.slice(0, MAX_TEXT);
    return clean(el.innerText || el.textContent || '').slice(0, MAX_TEXT);
  };
  const selectorHint = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    const test = ['data-testid','data-test','data-qa','name','aria-label','title','placeholder'];
    for (const a of test) {
      const v = el.getAttribute(a);
      if (v) return `${el.tagName.toLowerCase()}[${a}="${String(v).replace(/"/g, '\\"')}"]`;
    }
    return el.tagName.toLowerCase();
  };
  const isWatermark = (el, text) => {
    const style = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return text.length < 80 && Number(style.opacity || 1) <= 0.2 && r.width <= 220 && r.height <= 80;
  };
  const isClickable = (el) => {
    if (!visible(el)) return false;
    const tag = el.tagName;
    const role = clean(el.getAttribute('role')).toLowerCase();
    const style = getComputedStyle(el);
    if (['A','BUTTON','SUMMARY','OPTION'].includes(tag)) return true;
    if (['button','link','menuitem','tab','checkbox','radio','switch','option'].includes(role)) return true;
    if (el.hasAttribute('onclick')) return true;
    if (style.cursor === 'pointer') return true;
    return false;
  };
  const isInput = (el) => {
    if (!visible(el)) return false;
    if (['INPUT','TEXTAREA','SELECT'].includes(el.tagName)) return true;
    if (el.isContentEditable) return true;
    const role = clean(el.getAttribute('role')).toLowerCase();
    return ['textbox','combobox','searchbox'].includes(role);
  };
  const bodyText = clean(document.body ? document.body.innerText : '');
  const page = {
    url: location.href,
    title: document.title,
    body_text_head: bodyText.slice(0, 12000),
    is_login_like: /登录|login|sign in|corp邮箱|password|密码/i.test(bodyText),
    is_loading_like: /加载中|努力加载中|loading|please wait/i.test(bodyText)
  };
  const dialogs = [];
  for (const el of Array.from(document.querySelectorAll('[role=dialog], .modal, .dialog, [class*=modal], [class*=dialog], [class*=popover], [class*=drawer]'))) {
    if (!visible(el)) continue;
    const text = elementText(el);
    if (!text) continue;
    dialogs.push({text, tag: el.tagName, class: String(el.className || '').slice(0, 160), bbox: rectOf(el)});
    if (dialogs.length >= 20) break;
  }
  const clickables = [];
  const inputs = [];
  const all = Array.from(document.querySelectorAll('a,button,input,textarea,select,summary,[role],[onclick],[contenteditable],*[style*="cursor: pointer"],*[class*=btn],*[class*=button],*[class*=item],*[class*=card],*[class*=row]'));
  for (const el of all) {
    if (isInput(el)) {
      const text = elementText(el);
      inputs.push({
        id: inputs.length,
        tag: el.tagName,
        role: clean(el.getAttribute('role')),
        type: clean(el.getAttribute('type')),
        text,
        placeholder: clean(el.getAttribute('placeholder')),
        value_head: clean(el.value || el.innerText || '').slice(0, 160),
        enabled: !el.disabled,
        visible: true,
        bbox: rectOf(el),
        selector_hint: selectorHint(el)
      });
    }
    if (isClickable(el)) {
      const text = elementText(el);
      if (BAD_TEXT.has(text) || isWatermark(el, text)) continue;
      const href = el.href || el.getAttribute('href') || '';
      clickables.push({
        id: clickables.length,
        tag: el.tagName,
        role: clean(el.getAttribute('role')),
        text,
        aria_label: clean(el.getAttribute('aria-label')),
        title: clean(el.getAttribute('title')),
        href,
        enabled: !el.disabled && el.getAttribute('aria-disabled') !== 'true',
        visible: true,
        bbox: rectOf(el),
        selector_hint: selectorHint(el)
      });
    }
    if (clickables.length >= 300 && inputs.length >= 80) break;
  }
  return {page, dialogs, clickables: clickables.slice(0, 300), inputs: inputs.slice(0, 100)};
}
"""


def snapshot(page: Page) -> Dict[str, Any]:
    return page.evaluate(SNAPSHOT_JS)


def get_action_element(page: Page, kind: str, element_id: int):
    data = snapshot(page)
    arr = data["inputs"] if kind == "input" else data["clickables"]
    for item in arr:
        if int(item["id"]) == element_id:
            selector = item.get("selector_hint") or item["tag"].lower()
            return page.locator(selector).first, item
    raise RuntimeError(f"{kind} id not found in current snapshot: {element_id}")
