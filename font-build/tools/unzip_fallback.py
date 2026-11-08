#!/usr/bin/env python3
"""Minimal `unzip -o -j` replacement for environments without unzip
(e.g. Git Bash / MSYS2 on Windows, where Git for Windows ships no unzip).

Usage: unzip_fallback.py <zip> <pattern> [more patterns...]
Extracts members matching any pattern FLAT (junk paths, like unzip -j) into
the current directory, overwriting existing files (like unzip -o).
"""
import fnmatch
import os
import sys
import zipfile


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: unzip_fallback.py <zip> <pattern> [patterns...]")
    zip_path, patterns = sys.argv[1], sys.argv[2:]
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            base = os.path.basename(name)
            if any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(base, p)
                   for p in patterns):
                with z.open(info) as src, open(base, "wb") as dst:
                    dst.write(src.read())
                print(f"extracted {base} ({info.file_size / 1048576:.1f}MB)")
                n += 1
    if n == 0:
        sys.exit(f"ERROR: no member of {zip_path} matches {patterns}")


if __name__ == "__main__":
    main()
