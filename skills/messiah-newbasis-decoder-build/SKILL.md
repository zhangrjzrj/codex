---
name: "messiah-newbasis-decoder-build"
description: "Build Messiah/NewBasis decoder Windows artifacts with Conan, especially libNewBasisDecoder.dll from E:\\messiah_h74\\newbasis. Use when Codex needs to compile NewBasis decoder, package libNewBasisDecoder, refresh Conan dependencies, inspect build outputs, or sync decoder DLLs/PDB/libs for GUI/player validation."
---

# Messiah NewBasis Decoder Build

Use this skill for Windows `libNewBasisDecoder` builds from the local NewBasis source tree.

## Defaults

Configuration lives in `references/config.json`. Load it before running if the user asks for a non-default version.

Default version key:

```text
1.0.3
```

Default source and recipe:

```text
Source:  E:\messiah_h74\newbasis\NewBasisDecoder
Recipe:  E:\messiah_h74\buildscript\__V2__\ConanFiles\NewBasis\libNewBasisDecoder\1.0.3\testing
Workdir: E:\messiah_h74\buildscript
Build:   E:\messiah_h74\newbasis\tmp\conan.local.win.1.0.3.vs2022
```

`workdir` is normally fixed by `default_workdir`; keep it overrideable only for special cases.
`source_dir` is a validation hint for the local tree, not the main source-of-truth for Conan recipe selection.

Default Conan settings:

```text
remote=NeoX
build_type=RelWithDebInfo
shared=True
os=Windows
arch=x86_64
compiler=Visual Studio
compiler.version=17
compiler.runtime=MD
```

## Workflow

1. Check source changes:

```powershell
git -C 'E:\messiah_h74\newbasis' status --short --branch
```

2. Build with the bundled script:

```powershell
& 'C:\Users\zhangruojun\.codex\skills\messiah-newbasis-decoder-build\scripts\build-newbasis-decoder.ps1' -VersionKey '1.0.3' -Clean
```

Use `-ValidateOnly` to verify configuration without building.
Use `-ListVersions` to inspect configured versions.

3. Verify outputs:

```text
<build_dir>\package\bin\libNewBasisDecoder.dll
<build_dir>\package\lib\libNewBasisDecoder.lib
<build_dir>\package\pdb\libNewBasisDecoder.pdb
```

4. If the user asks to test in `F:\NBSEncoderGui`, treat copying/sync as a separate manual step. Do not overwrite GUI binaries unless explicitly requested.

## Important Notes

- Run Conan commands from `E:\messiah_h74\buildscript`.
- If links fail with `MT_StaticRelease` vs `MD_DynamicRelease`, remove the wrong Conan package ID and rerun `conan install`; do not manually copy `.lib` files between Conan packages.
- If `vpx.lib`, `libssl.lib`, or `libcrypto.lib` are missing or mismatched, use targeted `conan remove ... -p <package_id> -f`, then reinstall.
- Build success may still print many `LNK4099` missing PDB warnings from third-party static libraries; those warnings are acceptable if `libNewBasisDecoder.dll` is produced.
- `1.0.3_ST` is not the default local-source validation recipe; only use it when explicitly requested.
