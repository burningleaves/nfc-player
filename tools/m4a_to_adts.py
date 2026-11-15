#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io, os, argparse, struct

for _s in ('stdout', 'stderr'):
    _f = getattr(sys, _s, None)
    if _f is not None and hasattr(_f, 'reconfigure'):
        try:
            _f.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

SR_TABLE = [96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050,
             16000, 12000, 11025, 8000, 7350]

ELEMENT_LENGTH_TABLE = {
    0: 4, 1: 4, 2: 4, 3: 4, 4: 4, 5: 4, 6: 4, 7: 4,
    8: 4, 9: 4, 10: 4, 11: 4, 12: 4, 13: 4, 14: 4, 15: 4,
    16: 4, 17: 4, 18: 4, 19: 4, 20: 4, 21: 4, 22: 4, 23: 4,
    24: 4, 25: 4, 26: 4, 27: 4, 28: 4, 29: 4, 30: 4, 31: 4,
    32: 5, 33: 5, 34: 5, 35: 5, 36: 6, 37: 6, 38: 6, 39: 6,
    40: 7, 41: 7, 42: 7, 43: 7, 44: 8, 45: 8, 46: 8, 47: 8,
    48: 9, 49: 9, 50: 9, 51: 9, 52: 10, 53: 10, 54: 10, 55: 10,
    56: 11, 57: 11, 58: 11, 59: 11, 60: 11, 61: 11, 62: 11, 63: 11,
    64: 12, 65: 12, 66: 12, 67: 12, 68: 12, 69: 12, 70: 12, 71: 12,
    72: 13, 73: 13, 74: 13, 75: 13, 76: 13, 77: 13, 78: 13, 79: 13,
    80: 14, 81: 14, 82: 14, 83: 14, 84: 14, 85: 14, 86: 14, 87: 14,
    88: 15, 89: 15, 90: 15, 91: 15, 92: 15, 93: 15, 94: 15, 95: 15,
    96: 16, 97: 16, 98: 16, 99: 16, 100: 16, 101: 16, 102: 16, 103: 16,
    104: 17, 105: 17, 106: 17, 107: 17, 108: 17, 109: 17, 110: 17, 111: 17,
    112: 18, 113: 18, 114: 18, 115: 18, 116: 18, 117: 18, 118: 18, 119: 18,
    120: 19, 121: 19, 122: 19, 123: 19, 124: 19, 125: 19, 126: 19, 127: 19,
    128: 20, 129: 20, 130: 20, 131: 20, 132: 20, 133: 20, 134: 20, 135: 20,
    136: 20, 137: 20, 138: 20, 139: 20, 140: 20, 141: 20, 142: 20, 143: 20,
    144: 21, 145: 21, 146: 21, 147: 21, 148: 21, 149: 21, 150: 21, 151: 21,
    152: 21, 153: 21, 154: 21, 155: 21, 156: 21, 157: 21, 158: 21, 159: 21,
    160: 22, 161: 22, 162: 22, 163: 22, 164: 22, 165: 22, 166: 22, 167: 22,
    168: 22, 169: 22, 170: 22, 171: 22, 172: 22, 173: 22, 174: 22, 175: 22,
    176: 23, 177: 23, 178: 23, 179: 23, 180: 23, 181: 23, 182: 23, 183: 23,
    184: 23, 185: 23, 186: 23, 187: 23, 188: 23, 189: 23, 190: 23, 191: 23,
    192: 24, 193: 24, 194: 24, 195: 24, 196: 24, 197: 24, 198: 24, 199: 24,
    200: 24, 201: 24, 202: 24, 203: 24, 204: 24, 205: 24, 206: 24, 207: 24,
    208: 25, 209: 25, 210: 25, 211: 25, 212: 25, 213: 25, 214: 25, 215: 25,
    216: 25, 217: 25, 218: 25, 219: 25, 220: 25, 221: 25, 222: 25, 223: 25,
    224: 26, 225: 26, 226: 26, 227: 26, 228: 26, 229: 26, 230: 26, 231: 26,
    232: 26, 233: 26, 234: 26, 235: 26, 236: 26, 237: 26, 238: 26, 239: 26,
    240: 27, 241: 27, 242: 27, 243: 27, 244: 27, 245: 27, 246: 27, 247: 27,
    248: 27, 249: 27, 250: 27, 251: 27, 252: 27, 253: 27, 254: 27, 255: 27,
}


def parse_boxes(buf, off, end):
    out = []
    while off + 8 <= end:
        size = struct.unpack('>I', buf[off:off+4])[0]
        typ = buf[off+4:off+8]
        hdr = 8
        if size == 1:
            size = struct.unpack('>Q', buf[off+8:off+16])[0]
            hdr = 16
        elif size == 0:
            size = end - off
        if size < hdr:
            break
        out.append((typ, off, size, hdr))
        off += size
    return out


def adts_header(frame_len, sr_idx, chan):
    flen = frame_len + 7
    b = bytearray(7)
    b[0] = 0xFF
    b[1] = 0xF1
    b[2] = ((1 & 3) << 6) | (sr_idx << 2) | ((chan >> 2) & 1)
    b[3] = ((chan & 3) << 6) | ((flen >> 11) & 3)
    b[4] = (flen >> 3) & 0xFF
    b[5] = ((flen & 7) << 5) | 0x1F
    b[6] = 0xFC
    return bytes(b)


def extract_frames(buf):
    tops = parse_boxes(buf, 0, len(buf))
    pairs = []
    for i, (typ, off, size, hdr) in enumerate(tops):
        if typ != b'moof':
            continue
        region = buf[off:off+size]
        ti = region.find(b'trun')
        sizes = []
        if ti >= 4:
            tsz = struct.unpack('>I', region[ti-4:ti])[0]
            body = region[ti+4:ti-4+tsz]
            vf = struct.unpack('>I', body[0:4])[0]
            flags = vf & 0xFFFFFF
            cnt = struct.unpack('>I', body[4:8])[0]
            p = 8
            if flags & 0x01: p += 4
            if flags & 0x04: p += 4
            for _ in range(cnt):
                if flags & 0x100: p += 4
                if flags & 0x200:
                    sizes.append(struct.unpack('>I', body[p:p+4])[0])
                else:
                    sizes.append(0)
                if flags & 0x400: p += 4
                if flags & 0x800: p += 4
        j = i + 1
        while j < len(tops) and tops[j][0] == b'moof':
            j += 1
        if j < len(tops) and tops[j][0] == b'mdat' and sizes:
            m = tops[j]
            pairs.append((m[1] + m[3], m[1] + m[2], sizes))
    return pairs


def find_path(buf, path):
    off, end = 0, len(buf)
    for name in path:
        hit = None
        for typ, s, sz, h in parse_boxes(buf, off, end):
            if typ == name:
                hit = (s, sz, h)
                break
        if not hit:
            return None
        off = hit[0] + hit[2]
        end = hit[0] + hit[1]
    return hit


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='src', required=True)
    ap.add_argument('--out', dest='dst', required=True)
    args = ap.parse_args()
    if not os.path.isfile(args.src):
        print('input missing:', args.src)
        return 1
    buf = open(args.src, 'rb').read()
    print('read %s: %d bytes' % (args.src, len(buf)))
    stsd = find_path(buf, [b'moov', b'trak', b'mdia', b'minf', b'stbl', b'stsd'])
    if not stsd:
        print('no stsd')
        return 1
    region = buf[stsd[0]:stsd[0] + stsd[1]]
    ei = region.find(b'esds')
    if ei < 4:
        print('no esds (not AAC)')
        return 1
    esz = struct.unpack('>I', region[ei-4:ei])[0]
    seg = region[ei-4:ei-4+esz]
    k = seg.find(b'\x05')
    dsi_len = seg[k+1]
    dsi = seg[k+2:k+2+dsi_len]
    aot = (dsi[0] >> 3) & 0x1F
    sr_idx = ((dsi[0] & 0x07) << 1) | (dsi[1] >> 7)
    chan = (dsi[1] >> 3) & 0x0F
    sr = SR_TABLE[sr_idx] if sr_idx < len(SR_TABLE) else 0
    print('ASC: type=%d sr=%d ch=%d raw=%s' % (aot, sr, chan, dsi.hex()))
    pairs = extract_frames(buf)
    print('moof/mdat pairs: %d' % len(pairs))
    out = bytearray()
    nframes = 0
    for start, end, sizes in pairs:
        pos = start
        for sz in sizes:
            if sz <= 0 or pos + sz > end:
                break
            out += adts_header(sz, sr_idx, chan)
            out += buf[pos:pos+sz]
            pos += sz
            nframes += 1
    if not nframes:
        print('! no frames extracted')
        return 1
    with open(args.dst, 'wb') as f:
        f.write(bytes(out))
    print('wrote %s: %d bytes, %d frames' % (args.dst, len(out), nframes))
    if sr:
        print('  est duration %.1f s' % (nframes * 1024.0 / sr))
    return 0


if __name__ == '__main__':
    sys.exit(main())
