#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


CPP_SOURCE = r"""#include <iostream>
#include <string>
#include <OpenEXR/ImfInputFile.h>
#include <OpenEXR/ImfFloatAttribute.h>
#include <OpenEXR/ImfDoubleAttribute.h>
#include <OpenEXR/ImfIntAttribute.h>
#include <OpenEXR/ImfStringAttribute.h>
static bool readAttrAsDouble(const Imf::Header& header, const char* name, double& out){
  auto it = header.find(name);
  if(it==header.end()) return false;
  const Imf::Attribute& attr = it.attribute();
  std::string t = attr.typeName();
  if(t == Imf::FloatAttribute::staticTypeName()){ out = static_cast<const Imf::FloatAttribute&>(attr).value(); return true; }
  if(t == Imf::DoubleAttribute::staticTypeName()){ out = static_cast<const Imf::DoubleAttribute&>(attr).value(); return true; }
  if(t == Imf::IntAttribute::staticTypeName()){ out = static_cast<const Imf::IntAttribute&>(attr).value(); return true; }
  if(t == Imf::StringAttribute::staticTypeName()){ out = std::stod(static_cast<const Imf::StringAttribute&>(attr).value()); return true; }
  return false;
}
int main(int argc, char** argv){
  if(argc < 2){
    std::cerr << "need path\n";
    return 2;
  }
  try{
    Imf::InputFile f(argv[1]);
    const Imf::Header& h = f.header();
    double v = 0.0;
    if(readAttrAsDouble(h, "depth_flag", v)) std::cout << "depth_flag=" << v << "\n"; else std::cout << "depth_flag=<missing>\n";
    if(readAttrAsDouble(h, "MinDepth", v)) std::cout << "MinDepth=" << v << "\n"; else std::cout << "MinDepth=<missing>\n";
    if(readAttrAsDouble(h, "MaxDepth", v)) std::cout << "MaxDepth=" << v << "\n"; else std::cout << "MaxDepth=<missing>\n";
    if(readAttrAsDouble(h, "z_near", v)) std::cout << "z_near=" << v << "\n"; else std::cout << "z_near=<missing>\n";
    if(readAttrAsDouble(h, "z_far", v)) std::cout << "z_far=" << v << "\n"; else std::cout << "z_far=<missing>\n";
    return 0;
  }catch(const std::exception& e){
    std::cerr << "ERR " << e.what() << "\n";
    return 1;
  }
}
"""


def detect_vsdevcmd() -> Path:
    candidates = [
        Path(r"d:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"),
        Path(r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"),
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"),
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Professional\Common7\Tools\VsDevCmd.bat"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("VsDevCmd.bat not found")


def detect_openexr_root(override: str | None) -> Path:
    candidates = []
    if override:
        candidates.append(Path(override))
    candidates.extend(
        [
            Path(r"E:\messiah_h74\Encoder\NBSEncoder\source\library\openexr"),
            Path(r"F:\messiah_h74\Encoder\NBSEncoder\source\library\openexr"),
        ]
    )
    for candidate in candidates:
        include_dir = candidate / "include"
        lib_dir = candidate / "lib" / "release"
        if include_dir.exists() and lib_dir.exists():
            return candidate
    raise FileNotFoundError("OpenEXR root not found; pass --openexr-root")


def build_probe(script_dir: Path, openexr_root: Path) -> Path:
    cache_dir = script_dir / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cpp_path = cache_dir / "probe.cpp"
    exe_path = cache_dir / "probe.exe"
    bat_path = cache_dir / "build_probe.bat"
    lock_path = cache_dir / "build_probe.lock"

    if exe_path.exists():
        return exe_path

    lock_handle = acquire_lock(lock_path)
    try:
        if exe_path.exists():
            return exe_path

        cpp_path.write_text(CPP_SOURCE, encoding="ascii")

        include_dir = openexr_root / "include"
        lib_dir = openexr_root / "lib" / "release"
        vsdevcmd = detect_vsdevcmd()

        command = (
            "@echo off\n"
            f'call "{vsdevcmd}" -arch=x64 -host_arch=x64 >nul\n'
            f'pushd "{cache_dir}"\n'
            f'cl /nologo /MD /EHsc /std:c++17 /I "{include_dir}" "{cpp_path}" '
            f'/link /LIBPATH:"{lib_dir}" /DEFAULTLIB:legacy_stdio_definitions.lib '
            'IlmImf-2_4.lib Iex-2_4.lib IlmThread-2_4.lib Imath-2_4.lib Half-2_4.lib zlibstatic.lib '
            f'/OUT:"{exe_path}"\n'
            "set EXIT_CODE=%ERRORLEVEL%\n"
            "popd\n"
            "exit /b %EXIT_CODE%\n"
        )
        bat_path.write_text(command, encoding="ascii")

        proc = subprocess.run(
            ["cmd.exe", "/c", str(bat_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            cwd=str(cache_dir),
        )
        if proc.returncode != 0 or not exe_path.exists():
            sys.stderr.write(proc.stdout or "")
            sys.stderr.write(proc.stderr or "")
            raise RuntimeError("failed to build EXR probe")
        return exe_path
    finally:
        release_lock(lock_handle, lock_path)


def acquire_lock(lock_path: Path, timeout_seconds: float = 120.0):
    deadline = time.time() + timeout_seconds
    while True:
        try:
            return os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            if time.time() >= deadline:
                raise TimeoutError(f"timed out waiting for lock: {lock_path}")
            time.sleep(0.2)


def release_lock(lock_handle, lock_path: Path) -> None:
    os.close(lock_handle)
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def parse_probe_output(text: str) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value == "<missing>":
            result[key] = None
        else:
            result[key] = float(value)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Read key OpenEXR header attributes for Messiah EXR files")
    parser.add_argument("exr_path")
    parser.add_argument("--openexr-root", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    exr_path = Path(args.exr_path)
    if not exr_path.exists():
        print(f"EXR not found: {exr_path}", file=sys.stderr)
        return 2

    script_dir = Path(__file__).resolve().parent
    openexr_root = detect_openexr_root(args.openexr_root or None)
    exe_path = build_probe(script_dir, openexr_root)

    proc = subprocess.run(
        [str(exe_path), str(exr_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return proc.returncode

    if args.json:
        payload = {
            "path": str(exr_path),
            "openexr_root": str(openexr_root),
            "attributes": parse_probe_output(proc.stdout),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(proc.stdout, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
