# -*- coding: utf-8 -*-
import sys
import io

# Windows 控制台默认 GBK, 强制 UTF-8 输出避免中文乱码
for _s in ('stdout', 'stderr'):
    _f = getattr(sys, _s, None)
    if _f is not None and hasattr(_f, 'reconfigure'):
        try:
            _f.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
#!/usr/bin/env python3
"""
nfc_write.py -- 生成要写入 NFC 标签的 NDEF URI 记录。

用法:
    python nfc_write.py "https://example.github.io/nfc-player/?src=https://.../song.mp3"

它做三件事:
  1. 把 URL 编码成标准 NDEF URI 记录 (NFC Forum URI RTD 1.0, 带前缀缩写)
  2. 打印十六进制, 供支持"手动输入十六进制"的手机 App 使用
  3. 输出 .ndef 二进制文件, 供支持二进制导入的 App 使用

本机没有 USB NFC 读卡器时, 用安卓手机 App 写入:
    - "NFC Tag Writer" / "NFC Tools" / "NDEF Tag Editor"
    - 选择 URI 类型 -> 粘贴 URL -> 写入 -> 用手机贴到标签上
"""

import sys
import os
import struct

# NFC Forum URI RTD 1.0 前缀表: 索引 -> 固定前缀
URI_PREFIXES = {
    0x00: "",
    0x01: "http://www.",
    0x02: "https://www.",
    0x03: "http://",
    0x04: "https://",
    0x05: "tel:",
    0x06: "mailto:",
    0x07: "ftp://anonymous:anonymous@",
    0x08: "ftp://ftp.",
    0x09: "ftps://",
    0x0A: "sftp://",
    0x0B: "smb://",
    0x0C: "nfs://",
    0x0D: "ftp://",
    0x0E: "dav://",
    0x0F: "news:",
    0x10: "telnet://",
    0x11: "imap:",
    0x12: "rtsp://",
    0x13: "urn:",
    0x14: "pop:",
    0x15: "sip:",
    0x16: "sips:",
    0x17: "tftp:",
    0x18: "btspp://",
    0x19: "btl2cap://",
    0x1A: "btgoep://",
    0x1B: "tcpobex://",
    0x1C: "irdaobex://",
    0x1D: "file://",
    0x1E: "urn:epc:id:",
    0x1F: "urn:epc:tag:",
    0x20: "urn:epc:pat:",
    0x21: "urn:epc:raw:",
    0x22: "urn:epc:",
    0x23: "urn:nfc:",
}

PREFIX_INDEX = {v: k for k, v in URI_PREFIXES.items()}


def encode_ndef_uri(url: str) -> bytes:
    """把 URL 编码为 NDEF URI 记录 (MB/ME/SR/IL 均为 0, 单条记录)。"""
    # 找最长匹配的固定前缀
    best_prefix, best_idx = "", 0x00
    for idx, prefix in URI_PREFIXES.items():
        if prefix and url.lower().startswith(prefix.lower()):
            if len(prefix) > len(best_prefix):
                best_prefix, best_idx = prefix, idx

    remainder = url[len(best_prefix):]
    uri_bytes = remainder.encode("utf-8")

    # 第一个 payload 字节 = 前缀索引
    payload = bytes([best_idx]) + uri_bytes

    # NDEF record header:
    #   MB(1) ME(1) SR(1) IL(1) TNF(4)  -> TNF=0x01 (well-known)
    #   TYPE length(8) | payload length(8) | type | payload
    type_field = b"U"  # URI type
    flags = 0x40 | 0x10 | 0x01  # MB | SR | TNF=well-known
    header = bytes([flags, len(type_field), len(payload)])
    return header + type_field + payload


def hexdump(data: bytes) -> str:
    out = []
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        h = " ".join(f"{b:02X}" for b in chunk)
        out.append(f"{i:04X}  {h}")
    return "\n".join(out)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        print("ERROR: 需要提供 URL", file=sys.stderr)
        return 2

    url = sys.argv[1].strip()
    if not url.startswith(("http://", "https://", "mailto:", "tel:")):
        print(f"WARN: URL 没有已知前缀，将完整写入: {url}", file=sys.stderr)

    data = encode_ndef_uri(url)

    print("=" * 68)
    print("NFC NDEF URI 记录")
    print("=" * 68)
    print(f"URL      : {url}")
    print(f"总长度   : {len(data)} 字节")
    print(f"可用容量 : NTAG213=144 / NTAG215=504 / NTAG216=888 字节 -> "
          f"{'OK' if len(data) <= 144 else '超出 NTAG213!'}")
    print()
    print("HEX (无 CAPTCHUNK, 可直接喂给支持十六进制输入的 App):")
    print(hexdump(data))
    print()
    print("紧凑 HEX:")
    print(data.hex().upper())
    print()

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tag.ndef")
    with open(out, "wb") as f:
        f.write(data)
    print(f"已写出二进制: {out}")
    print()
    print("写入方式 (二选一):")
    print("  A. 手机 App: NFC Tools / NDEF Tag Editor -> 新建记录 -> 类型选 URI ->")
    print(f"     粘贴 URL -> 保存 -> 用手机背面贴近标签")
    print(f"  B. 支持十六进制输入的 App: 粘贴上面「紧凑 HEX」")
    print("  C. 带 USB NFC 读卡器的 PC: 用 nfcpy 或 NFC Tools CLI 写 .ndef 文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
