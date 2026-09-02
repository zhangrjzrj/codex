import argparse
import struct
import subprocess
from pathlib import Path


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("captured file is not a valid PNG")
    return struct.unpack(">II", data[16:24])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh-host", default="mac-h74")
    parser.add_argument("--udid", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--python", default="/Applications/Xcode.app/Contents/Developer/usr/bin/python3")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    remote_path = f"/tmp/j_iphone_screenshot_{args.udid.replace('-', '')}.png"
    capture_command = (
        f"{args.python} -m pymobiledevice3 developer dvt screenshot "
        f"--userspace --udid {args.udid} {remote_path}"
    )
    subprocess.run(["ssh", args.ssh_host, capture_command], check=True)
    subprocess.run(["scp", f"{args.ssh_host}:{remote_path}", str(output)], check=True)

    width, height = png_dimensions(output)
    if width < 1 or height < 1:
        raise ValueError(f"invalid PNG dimensions: {width}x{height}")
    print(f"CAPTURE_OK path={output} size={output.stat().st_size} dimensions={width}x{height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
