# Public Develop iOS C++ Telnet

Use this reference when an iOS public-develop worktree has no reliable runtime Telnet listener on port `9113`.

## Archived patch

- File: `../assets/patches/public-develop-ios-cpp-telnet-73ed96ef.patch`
- Verified source commit: `73ed96ef660b78fd7cbbadb1803b5c4166466935`
- Verified mode: iOS Hybrid, bundle `com.netease.technicalcenter`
- Verified device route: CoreDevice IPv6 `[fd37:3299:ca8::1]:9113`

The patch is a public-baseline artifact, not a universal Messiah patch. It changes seven files under Asyncore and Python. Do not use fuzzy application, reject files, or three-way fallback to force it onto another code line.

## Why it works

```text
Python runtime path becomes valid
-> C++ owns a persistent Telnet server
-> listen socket is created synchronously
-> [::]:9113 accepts the CoreDevice IPv6 route
-> text frames are handled immediately in C++
-> script commands keep using the external Python callback
```

The implementation invariants are:

1. Asyncore owns the server pointer and stops it with the async runtime.
2. `listen_immediate()` performs the initial server start before returning; it does not leave listener creation waiting behind later game work.
3. Bind to `::`, not an IPv4-only address.
4. `TELNET_CMD_TEXT` runs directly in the connection path so greeting and echo do not wait for the external Python queue. Other commands retain that queue.
5. Python home points to `Package/Script/Python/Lib314` through `builtin_home`.
6. Duplicate startup entry points are safe because both async runtime and Telnet server startup are idempotent.

## Applicability gate

Run from the Messiah repository root:

```bash
PATCH=/absolute/path/public-develop-ios-cpp-telnet-73ed96ef.patch
git apply --check "$PATCH"
```

Proceed only when the check exits zero. Before applying, also require:

- the seven target files exist;
- the worktree has no overlapping changes in those files;
- the user has authorized source modification;
- the staged area remains untouched.

Apply only after those gates pass:

```bash
git apply "$PATCH"
git diff --check -- \
  Engine/Sources/Runtime/Plugins/Asyncore/Sources \
  Engine/Sources/Runtime/Plugins/Python/Source/MPython.cpp
```

If the check fails, stop and port the six invariants above to the actual version by reading its lifecycle and networking code. Do not partially apply the archive.

## Build and runtime acceptance

After the ordinary signed Hybrid build, installation, registration, and launch gates pass:

1. Discover the current CoreDevice tunnel address; do not assume the archived IPv6 address is stable.
2. Connect directly to `[device-ipv6]:9113` first.
3. Require `Welcome to messiah server`.
4. Send a unique text marker.
5. Require the same marker in the response.

The Telnet gate passes only when both are true:

```text
HANDSHAKE_OK=True
RX_OK=True
```

`BUILD SUCCEEDED`, an installed app, a running process, or an open TCP socket alone is not Telnet success.

Homebrew `iproxy` is an optional compatibility route. If it reports `libusbmuxd error opening socket`, use CoreDevice IPv6 direct access rather than retrying the same forwarding path.
