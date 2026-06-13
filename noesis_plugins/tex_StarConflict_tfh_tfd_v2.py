# Star Conflict TFH/TFD - enhanced v2 + font support
# ================================================================
# v2.1: font format detection (24-byte TFH)
#   R8  (fmt_b1=0xA0/0x00): 1 byte/pixel luminance
#   A8L8 (fmt_b1=0xA2): 2 byte/pixel alpha+luminance interleaved
#   ARGB (fmt_b1=0xA5): 4 byte/pixel alpha+color (A,R,G,B order)
# Original v2 logic: bitstream header + mip table for compressed textures
# ================================================================
from inc_noesis import *
import math, struct

FMT_MAP = {
    0x7: noesis.NOESISTEX_DXT1, 0xB: noesis.NOESISTEX_DXT1,
    0x8: noesis.NOESISTEX_DXT1, 0xC: noesis.NOESISTEX_DXT1,
    0x9: noesis.NOESISTEX_DXT3, 0xD: noesis.NOESISTEX_DXT3,
    0xA: noesis.NOESISTEX_DXT5, 0xE: noesis.NOESISTEX_DXT5,
    0x4: noesis.NOESISTEX_DXT5, 0x6: noesis.NOESISTEX_DXT5,
    0x3: noesis.NOESISTEX_DXT5,
}

def registerNoesisTypes():
    handle = noesis.register("Star Conflict", ".tfh")
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadRGBA(handle, noepyLoadRGBA)
    return 1

def noepyCheckType(data):
    return 1

def calc_mip(w, h, block):
    return ((w + 3) // 4) * ((h + 3) // 4) * block

def guess_size(tfd_len):
    best_w, best_h, best_block = 64, 64, 16
    for s in [32, 64, 128, 256, 512, 1024, 2048, 4096]:
        need5 = calc_mip(s, s, 16)
        need1 = calc_mip(s, s, 8)
        if need5 <= tfd_len * 1.5:
            best_w, best_h, best_block = s, s, 16
        elif need1 <= tfd_len * 1.2:
            if best_block != 16 or (tfd_len > 4000000 and s > best_w):
                best_w, best_h, best_block = s, s, 8
    return best_w, best_h, best_block

# ================================================================
# Font parser (24-byte TFH header)
# ================================================================
def parse_font_tfh(data):
    """Parse 24-byte font TFH. Returns (fmt_type, datasize, byte_width, px_width, px_height) or None."""
    if len(data) != 24:
        return None
    datasize = struct.unpack_from('<I', data, 12)[0]
    byte_width = struct.unpack_from('<I', data, 16)[0]
    fmt_val = struct.unpack_from('<I', data, 4)[0]
    fmt_b1 = (fmt_val >> 8) & 0xFF

    if byte_width <= 0 or datasize <= 0:
        return None

    px_h = datasize // byte_width

    if fmt_b1 == 0xA5:
        return ('ARGB', datasize, byte_width, byte_width // 4, px_h)
    elif fmt_b1 == 0xA2:
        return ('A8L8', datasize, byte_width, byte_width // 2, px_h)
    else:
        return ('R8', datasize, byte_width, byte_width, px_h)

def load_font_texture(tfh_data, tfh_path):
    """Load font texture. tfh_data = raw TFH bytes, tfh_path = file path for TFD lookup."""
    tfd_path = rapi.getExtensionlessName(tfh_path) + ".tfd"
    try:
        tfd_raw = rapi.loadIntoByteArray(tfd_path)
    except:
        try:
            with open(tfd_path, 'rb') as f:
                tfd_raw = f.read()
        except:
            print("ERROR: Cannot open TFD for font: %s" % tfd_path)
            return None

    result = parse_font_tfh(tfh_data)
    if result is None:
        return None

    fmt_type, datasize, byte_width, px_w, px_h = result

    # Read pixel data
    need = min(datasize, len(tfd_raw))
    raw = tfd_raw[:need]

    # Convert to RGBA32
    rgba = bytearray(px_w * px_h * 4)

    if fmt_type == 'R8':
        for i in range(px_w * px_h):
            v = raw[i] if i < len(raw) else 0
            rgba[i*4] = v
            rgba[i*4+1] = v
            rgba[i*4+2] = v
            rgba[i*4+3] = 255
    elif fmt_type == 'A8L8':
        for i in range(px_w * px_h):
            if i * 2 + 1 < len(raw):
                a = raw[i*2]      # alpha (first byte)
                l = raw[i*2+1]    # luminance (second byte)
            else:
                a = 255
                l = 0
            rgba[i*4] = l
            rgba[i*4+1] = l
            rgba[i*4+2] = l
            rgba[i*4+3] = a
    else:  # ARGB (A,R,G,B order)
        for i in range(px_w * px_h):
            if i * 4 + 3 < len(raw):
                a = raw[i*4]
                r = raw[i*4+1]
                g = raw[i*4+2]
                b = raw[i*4+3]
            else:
                r = g = b = 0
                a = 255
            rgba[i*4] = r
            rgba[i*4+1] = g
            rgba[i*4+2] = b
            rgba[i*4+3] = a

    return bytes(rgba), px_w, px_h

# ================================================================
# Main loader
# ================================================================
def noepyLoadRGBA(data, texList):
    tfhPath = rapi.getInputName()

    # === Font detection: 24-byte TFH header ===
    if len(data) == 24:
        result = load_font_texture(data, tfhPath)
        if result is not None:
            rgba, w, h = result
            texList.append(NoeTexture(tfhPath, w, h, rgba, noesis.NOESISTEX_RGBA32))
            return 1
        # Fall through to standard texture parsing if font load fails

    # === Original v2 logic for compressed textures ===
    bs = NoeBitStream(data)
    bs.readBits(4)
    imgWidth = bs.readBits(12)
    imgHeight = bs.readUShort() // 4
    mips = bs.readBits(4)
    bs.readBits(4)
    imgFmt = bs.readBits(4)
    bs.readBits(4)
    bs.readBytes(2)
    tfdFile = rapi.getExtensionlessName(rapi.getInputName()) + ".tfd"
    print("%dx%d fmt=0x%X mips=%d" % (imgWidth, imgHeight, imgFmt, mips))

    # --- Fallback: only if dimensions are clearly garbage ---
    if imgWidth <= 0 or imgHeight <= 0 or imgWidth > 8192 or imgHeight > 8192:
        print("[fallback] bitstream invalid, using TFD size")
        try:
            tfdRaw = rapi.loadIntoByteArray(tfdFile)
            tfdLen = len(tfdRaw)
        except:
            print("ERROR: Cannot open TFD")
            return 0
        w, h, block = guess_size(tfdLen)
        if "sai" in tfdFile.lower():
            w = h = 4096; block = 8
        mainSize = calc_mip(w, h, block)
        for off in [tfdLen - mainSize, 0]:
            if off >= 0 and off + mainSize <= tfdLen:
                break
        if mainSize > tfdLen: mainSize = tfdLen
        texFmt = noesis.NOESISTEX_DXT5 if block == 16 else noesis.NOESISTEX_DXT1
        data = tfdRaw[off:off + mainSize]
        print("[fallback] %dx%d %s off=%d" % (w, h, "DXT5" if block==16 else "DXT1", off))
        texList.append(NoeTexture(rapi.getInputName(), w, h, data, texFmt))
        return 1

    # --- Original v2 logic ---
    bs2 = NoeBitStream(rapi.loadIntoByteArray(tfdFile))
    if mips > 0:
        bs.seek((mips * 12) - 12, NOESEEK_REL)
        mainMipOffset = bs.readUInt()
        datasize = bs.readUInt()
        imgSize = bs.readUInt()
    else:
        mainMipOffset = 0
        datasize = 0
    if datasize <= 0:
        try: datasize = bs2.getSize()
        except: datasize = 2097152

    bs2.seek(mainMipOffset, NOESEEK_ABS)

    texFmt = FMT_MAP.get(imgFmt, noesis.NOESISTEX_DXT5)

    if imgFmt == 0xe and imgWidth == 0:
        imgWidth = int(math.sqrt(datasize))
        imgHeight = imgWidth
        texFmt = noesis.NOESISTEX_DXT5
    elif imgFmt == 0xe and imgWidth != 0:
        texFmt = noesis.NOESISTEX_DXT5

    try:
        data = bs2.readBytes(datasize)
    except:
        data = bs2.readBytes(min(datasize, 2097152))

    texList.append(NoeTexture(rapi.getInputName(), imgWidth, imgHeight, data, texFmt))
    return 1
