from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from playwright.sync_api import BrowserContext, Page, sync_playwright


@dataclass(frozen=True)
class RunPaths:
    out_dir: Path
    screenshots_dir: Path
    downloads_dir: Path
    result_path: Path


def _ensure_dirs(out_dir: Path) -> RunPaths:
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir = out_dir / "screenshots"
    downloads_dir = out_dir / "downloads"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir.mkdir(parents=True, exist_ok=True)
    return RunPaths(
        out_dir=out_dir,
        screenshots_dir=screenshots_dir,
        downloads_dir=downloads_dir,
        result_path=out_dir / "result.json",
    )


def _safe_ext_from_url(url: str) -> str:
    path = urlparse(url).path
    ext = Path(path).suffix
    if not ext:
        return ".bin"
    if re.fullmatch(r"\.[A-Za-z0-9]{1,8}", ext):
        return ext
    return ".bin"


def _normalize_img_url(page_url: str, src: str) -> str:
    if not src:
        return ""
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        parsed = urlparse(page_url)
        return f"{parsed.scheme}://{parsed.netloc}{src}"
    return src


def _click_role(page: Page, role: str, name: str) -> None:
    page.get_by_role(role, name=re.compile(re.escape(name), re.I)).click()


def _extract_text(page: Page, selector: str) -> str:
    loc = page.locator(selector).first
    return loc.inner_text()


def _extract_title(page: Page) -> str:
    return page.title()


def _download_img(
    context: BrowserContext,
    page: Page,
    paths: RunPaths,
    name: str,
    selector: str,
    timeout_ms: int,
) -> str:
    page.wait_for_selector(selector, timeout=timeout_ms)
    loc = page.locator(selector).first
    src = loc.get_attribute("src") or ""
    src = _normalize_img_url(page.url, src)
    if not src:
        raise RuntimeError(f"download_img: src empty for selector={selector!r}")

    ext = _safe_ext_from_url(src)
    out_path = paths.downloads_dir / f"{name}{ext}"
    resp = context.request.get(src)
    if not resp.ok:
        raise RuntimeError(f"download_img: http {resp.status} url={src}")
    out_path.write_bytes(resp.body())
    return str(out_path)


def run(
    spec: Dict[str, Any],
    out_dir: Path,
    state: Optional[Path],
    *,
    headless: bool,
) -> Dict[str, Any]:
    paths = _ensure_dirs(out_dir)
    result: Dict[str, Any] = {"url": spec.get("url", ""), "steps": [], "extracted": {}}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=str(state) if state else None)
        page = context.new_page()

        url = str(spec["url"])
        page.goto(url, wait_until="domcontentloaded")

        for idx, step in enumerate(spec.get("steps", [])):
            step_type = step.get("type")
            step_rec: Dict[str, Any] = {"index": idx, "type": step_type}

            try:
                if step_type == "wait_network_idle":
                    page.wait_for_load_state("networkidle")
                elif step_type == "wait_selector":
                    page.wait_for_selector(
                        step["selector"],
                        timeout=int(step.get("timeout_ms", 30000)),
                        state=str(step.get("state", "visible")),
                    )
                elif step_type == "click":
                    timeout_ms = int(step.get("timeout_ms", 30000))
                    force = bool(step.get("force", False))
                    page.locator(step["selector"]).first.click(timeout=timeout_ms, force=force)
                elif step_type == "click_role":
                    _click_role(page, step["role"], step["name"])
                elif step_type == "fill":
                    timeout_ms = int(step.get("timeout_ms", 30000))
                    force = bool(step.get("force", False))
                    page.locator(step["selector"]).first.fill(step["text"], timeout=timeout_ms, force=force)
                elif step_type == "press":
                    page.keyboard.press(step["key"])
                elif step_type == "eval":
                    # Run a small JS snippet in page context.
                    # Example: {"type":"eval","script":"document.querySelector('#kw').value='x'"}
                    page.evaluate(str(step["script"]))
                elif step_type == "screenshot":
                    filename = step.get("path") or f"step_{idx}.png"
                    out_path = paths.screenshots_dir / filename
                    page.screenshot(path=str(out_path), full_page=bool(step.get("full_page", False)))
                    step_rec["path"] = str(out_path)
                elif step_type == "extract_text":
                    name = step["name"]
                    text = _extract_text(page, step["selector"])
                    result["extracted"][name] = text
                    step_rec["name"] = name
                elif step_type == "extract_title":
                    name = step.get("name", "title")
                    text = _extract_title(page)
                    result["extracted"][name] = text
                    step_rec["name"] = name
                elif step_type == "download_img":
                    name = step["name"]
                    timeout_ms = int(step.get("timeout_ms", 30000))
                    saved = _download_img(context, page, paths, name, step["selector"], timeout_ms)
                    step_rec["name"] = name
                    step_rec["path"] = saved
                else:
                    raise ValueError(f"unknown step type: {step_type!r}")

                step_rec["page_url"] = page.url
                step_rec["ok"] = True
            except Exception as e:
                # Always drop a screenshot on failure for debugging.
                fail_path = paths.screenshots_dir / f"fail_step_{idx}.png"
                try:
                    page.screenshot(path=str(fail_path), full_page=True)
                    step_rec["fail_screenshot"] = str(fail_path)
                except Exception:
                    pass
                step_rec["ok"] = False
                step_rec["error"] = str(e)
                result["steps"].append(step_rec)
                break

            result["steps"].append(step_rec)

        paths.result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        browser.close()

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, help="Path to spec JSON.")
    parser.add_argument("--out", required=True, help="Output directory.")
    parser.add_argument("--state", default="", help="Optional storage_state JSON from login_once.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--headless", action="store_true", help="Run in headless mode (default).")
    mode.add_argument("--headful", action="store_true", help="Run in normal mode (shows browser window).")
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    out_dir = Path(args.out).resolve()
    state_path = Path(args.state).resolve() if args.state else None
    headless = not args.headful

    # Allow Windows tools to write UTF-8 with BOM.
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    result = run(spec, out_dir=out_dir, state=state_path, headless=headless)
    print(out_dir)
    if result["steps"] and not result["steps"][-1].get("ok", True):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
