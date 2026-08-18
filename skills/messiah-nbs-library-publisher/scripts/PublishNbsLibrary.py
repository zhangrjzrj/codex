#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


LIB_DIR = Path("Engine/Sources/External/miniGif/lib")
HEADER_DIR = Path("Engine/Sources/External/miniGif/include/nbs")
NBSEXTEND_DIR = Path("Engine/Sources/External/nbsextend/lib")


@dataclass(frozen=True)
class CopyOp:
    src: Path
    dst: Path


def _require_dir(path: Path, label: str) -> None:
    if not path.is_dir():
        raise SystemExit(f"{label}不存在: {path}")


def _find_single_dir(root: Path, prefix: str) -> Path:
    matches = [p for p in root.iterdir() if p.is_dir() and p.name.startswith(prefix)]
    if not matches:
        raise FileNotFoundError(f"未找到目录前缀 {prefix} 于 {root}")
    if len(matches) > 1:
        names = ", ".join(p.name for p in matches)
        raise FileNotFoundError(f"目录前缀 {prefix} 命中多个候选: {names}")
    return matches[0]


def _require_file(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"缺少文件: {path}")
    return path


def _build_ops(staging_root: Path, engine_root: Path, ps5_variant: str, include_asan: bool) -> list[CopyOp]:
    ops: list[CopyOp] = []

    def add(src: Path, dst_rel: Path) -> None:
        ops.append(CopyOp(_require_file(src), engine_root / dst_rel))

    def add_platform_header(platform_root: Path) -> None:
        include_dir = _find_single_dir(platform_root, "libNewBasisDecoder-").joinpath("include", "nbs")
        for header in sorted(include_dir.glob("*.h")):
            add(header, HEADER_DIR / header.name)

    add_platform_header(staging_root / "win-RelWithDebInfo-MD")

    android_map = {
        "Android_arm64": "arm64-v8a",
        "Android_armv7": "armeabi-v7a",
        "Android_x64": "x86_64",
        "Android_x86": "x86",
    }
    for platform, abi in android_map.items():
        platform_root = staging_root / platform
        decoder_dir = _find_single_dir(platform_root, "libNewBasisDecoder-")
        add(decoder_dir / "lib" / "libNewBasisDecoder.a", LIB_DIR / "android" / abi / "release" / "libNewBasisDecoder.a")
        extend_dir = _find_single_dir(platform_root, "nbs_extend-")
        add(extend_dir / "lib" / "libnbsextend.so", NBSEXTEND_DIR / "android" / abi / "release" / "libnbsextend.so")

    ios_root = staging_root / "ios"
    ios_decoder = _find_single_dir(ios_root, "libNewBasisDecoder-")
    add(ios_decoder / "lib" / "libNewBasisDecoder.a", LIB_DIR / "ios" / "arm64" / "release" / "libNewBasisDecoder.a")

    mac_arm_root = staging_root / "mac-arm"
    mac_arm_decoder = _find_single_dir(mac_arm_root, "libNewBasisDecoder-")
    add(mac_arm_decoder / "lib" / "libNewBasisDecoder.a", LIB_DIR / "mac" / "arm64" / "release" / "libNewBasisDecoder.a")

    win_md_root = staging_root / "win-RelWithDebInfo-MD"
    win_md_decoder = _find_single_dir(win_md_root, "libNewBasisDecoder-")
    add(win_md_decoder / "bin" / "libNewBasisDecoder.dll", LIB_DIR / "windows" / "x64" / "develop" / "libNewBasisDecoder.dll")
    add(win_md_decoder / "lib" / "libNewBasisDecoder.lib", LIB_DIR / "windows" / "x64" / "develop" / "libNewBasisDecoder.lib")
    add(win_md_decoder / "pdb" / "libNewBasisDecoder.pdb", LIB_DIR / "windows" / "x64" / "develop" / "libNewBasisDecoder.pdb")

    win_mt_root = staging_root / "win-RelWithDebInfo-MT"
    win_mt_decoder = _find_single_dir(win_mt_root, "libNewBasisDecoder-")
    add(win_mt_decoder / "lib" / "libNewBasisDecoder.lib", LIB_DIR / "windows" / "x64" / "release" / "libNewBasisDecoder.lib")

    win_static_md_root = staging_root / "win-RelWithDebInfo-static-MD"
    win_static_md_decoder = _find_single_dir(win_static_md_root, "libNewBasisDecoder-")
    add(win_static_md_decoder / "lib" / "libNewBasisDecoder.lib", LIB_DIR / "windows" / "x64" / "release-md" / "libNewBasisDecoder.lib")

    if include_asan:
        win_asan_root = staging_root / "windows-asan"
        win_asan_hybrid = _find_single_dir(win_asan_root, "hybrid")
        win_asan_release = _find_single_dir(win_asan_root, "release")
        add(win_asan_hybrid / "libNewBasisDecoder.dll", LIB_DIR / "windows" / "asan-windows" / "hybrid" / "libNewBasisDecoder.dll")
        add(win_asan_hybrid / "libNewBasisDecoder.pdb", LIB_DIR / "windows" / "asan-windows" / "hybrid" / "libNewBasisDecoder.pdb")
        add(win_asan_release / "libNewBasisDecoder.lib", LIB_DIR / "windows" / "asan-windows" / "release" / "libNewBasisDecoder.lib")

    win_extend = _find_single_dir(win_md_root, "nbs_extend-")
    for subdir in ("develop", "release"):
        add(win_extend / "bin" / "nbsextend.dll", NBSEXTEND_DIR / "windows" / "x64" / subdir / "nbsextend.dll")
        add(win_extend / "pdb" / "nbsextend.pdb", NBSEXTEND_DIR / "windows" / "x64" / subdir / "nbsextend.pdb")

    ps5_root = staging_root / f"PS5-{ps5_variant}"
    ps5_decoder = _find_single_dir(ps5_root, "libNewBasisDecoder-")
    add(ps5_decoder / "bin" / "libNewBasisDecoder.prx", LIB_DIR / "prospero" / "release" / "libNewBasisDecoder.prx")
    add(ps5_decoder / "lib" / "libNewBasisDecoder_stub_weak.a", LIB_DIR / "prospero" / "release" / "libNewBasisDecoder_stub_weak.a")

    return ops


def _apply_ops(ops: list[CopyOp], dry_run: bool) -> None:
    for op in ops:
        print(f"{op.src} -> {op.dst}")
        if dry_run:
            continue
        op.dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(op.src, op.dst)


def _extract_archive(archive_path: Path, staging_root: Path) -> None:
    suffix = archive_path.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(staging_root)
        return
    if suffix == ".7z":
        seven_zip = shutil.which("7z")
        if seven_zip is None:
            default_seven_zip = Path("C:/Program Files/7-Zip/7z.exe")
            if not default_seven_zip.is_file():
                raise SystemExit("未找到 7z.exe，无法解压 .7z 交付包")
            seven_zip = str(default_seven_zip)
        subprocess.run(
            [seven_zip, "x", str(archive_path), f"-o{staging_root}", "-y"],
            check=True,
        )
        return
    raise SystemExit(f"不支持的压缩包格式: {archive_path.suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description="从 NBS ZIP/7z 包向 Messiah 引擎发布库文件")
    parser.add_argument("archive_path", help="下载的 NBS 库 ZIP 或 7z 路径")
    parser.add_argument("engine_root", help="Messiah 引擎根路径，例如 F:\\messiah_official\\messiah_develop")
    parser.add_argument("--ps5-variant", choices=["12", "13"], required=True, help="PS5 发布变体，只能二选一")
    parser.add_argument("--asan", action="store_true", help="同时发布 Windows ASAN Hybrid/Release 变体")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不落文件")
    args = parser.parse_args()

    archive_path = Path(args.archive_path).resolve()
    engine_root = Path(args.engine_root).resolve()
    if not archive_path.is_file():
        raise SystemExit(f"压缩包不存在: {archive_path}")
    _require_dir(engine_root, "引擎根目录")
    _require_dir(engine_root / "Engine" / "Sources" / "External" / "miniGif", "miniGif目录")
    _require_dir(engine_root / "Engine" / "Sources" / "External" / "nbsextend", "nbsextend目录")

    with tempfile.TemporaryDirectory(prefix="publish_nbs_") as temp_dir:
        staging_root = Path(temp_dir) / "archive"
        _extract_archive(archive_path, staging_root)
        children = list(staging_root.iterdir())
        archive_root = children[0] if len(children) == 1 and children[0].is_dir() else staging_root
        ops = _build_ops(archive_root, engine_root, args.ps5_variant, args.asan)
        _apply_ops(ops, args.dry_run)

    print(f"完成，共处理 {len(ops)} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
