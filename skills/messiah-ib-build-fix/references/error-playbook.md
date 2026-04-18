# Error Playbook

Use this file when iterating on Messiah Windows compile failures.

## Loop discipline

1. Fix only top one to three high-confidence errors from the latest parsed report.
2. Rebuild immediately after patching; do not stack speculative edits.
3. Stop after two rounds with identical top signatures and report blocker context.

## Common compiler patterns

- `C2065` undeclared identifier:
  - Check missing include or namespace qualification.
  - Verify macro guards and build config specific defines.

- `C2146` / `C4430` missing type specifier:
  - Resolve the first parse error in file order.
  - Add forward declaration only when type usage allows incomplete type.

- `C2664` / `C2440` conversion mismatch:
  - Inspect signature changes in called API.
  - Prefer explicit cast only when ownership/lifetime are safe.

- `LNK2001` / `LNK2019` unresolved external:
  - Confirm declaration/definition signature match.
  - Check target `.vcxproj` source inclusion and conditional compile flags.
  - Verify dependent libraries in project link inputs.

- `LNK1104` cannot open file:
  - Verify output artifact path exists.
  - Check whether prior compile errors prevented dependent lib generation.
  - Confirm local path and permission issues before code changes.

- `MSB3073` custom build command failure:
  - Open the referenced command output from same log region.
  - Treat this as wrapper failure; fix underlying command/tool error first.

## High-risk changes to avoid in auto-fix mode

- Broad refactors unrelated to current error signatures.
- Mass include rewrites across many modules.
- Build-system or dependency version upgrades.
- Any destructive git action unless explicitly requested.

