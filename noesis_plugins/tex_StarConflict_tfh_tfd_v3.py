# Star Conflict TFH/TFD - v3: PHP mip-table parsing + v2 fallback
# ================================================================
# v3: PHP TargemImage.php byte-level mip table parsing (correct for
#     non-square textures like _s1 BC5/ATI2), plus v2 fallback.
# v2: bitstream header + mip table for compressed textures.
# v2.1: font format detection (24-byte TFH).
# ================================================================
from inc_noesis import *
import math, struct

# ================================================================
# v2 helper functions (used by fallback and font loader)
# ================================================================
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
# Noesis plugin registration
# ================================================================
def registerNoesisTypes():
    handle = noesis.register("Star Conflict v3", ".tfh")
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadRGBA(handle, noepyLoadRGBA)
    return 1

def noepyCheckType(data):
    return 1

# ================================================================
# Font parser (24-byte TFH header) — same as v2
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
# PHP-style mip table header parser (byte-level, no bitstream)
# ================================================================
def parse_tfh_php(data):
    """
    Parse TFH using PHP TargemImage.php byte-level logic.
    Returns (w, h, texFmt, pixel_data, fmt_hex, mipsCount, mipsInFile)
    or None if parsing fails or produces invalid dimensions.
    """
    if len(data) < 8:
        return None

    # --- PHP-style 8-byte header ---
    # Bytes 0-3: imageSize (u32 LE, informational only)
    imageSize = struct.unpack_from('<I', data, 0)[0]
    # Byte 4: mips byte → mipsCount (lower nibble), mipsInFile (upper nibble)
    mips_raw = data[4]
    mipsCount = mips_raw & 0x0F
    mipsInFile = (mips_raw & 0xF0) >> 4
    # Byte 5: format_raw (u8) → format = format_raw & 0x0F
    fmt_raw = data[5]
    fmt = fmt_raw & 0x0F
    # Byte 6-7: type, unknown2 (informational)
    type_byte = data[6]
    unknown2 = data[7]

    # --- PHP-style mip table: mipsCount entries, each = (u32 offset, u32 size, u32 width) ---
    mip_entry_size = 12  # 3 x u32
    mip_table_end = 8 + mipsCount * mip_entry_size
    if len(data) < mip_table_end or mipsCount == 0:
        return None

    last_idx = mipsCount - 1
    mip_off = 8 + last_idx * mip_entry_size
    mip_offset, mip_size, mip_width = struct.unpack_from('<III', data, mip_off)

    if mip_size <= 0 or mip_width <= 0:
        return None

    # --- Calculate pixel dimensions from mip table ---
    if fmt in (0x0, 0x5, 0x6):
        # RGBA uncompressed
        pixel_w = mip_width // 4
        pixel_h = mip_size // mip_width
    elif fmt in (0x7, 0x8, 0xB, 0xC):
        # DXT1: 8 bytes per 4x4 block
        pixel_w = mip_width // 2
        pixel_h = (4 * mip_size) // mip_width
    elif fmt in (0x9, 0xD):
        # DXT3
        pixel_w = mip_width // 4
        pixel_h = (4 * mip_size) // mip_width
    elif fmt in (0x3, 0x4, 0xA, 0xE):
        # DXT5
        pixel_w = mip_width // 4
        pixel_h = (4 * mip_size) // mip_width
    else:
        # Unknown format — fall through to fallback
        return None

    # --- Validate dimensions ---
    if pixel_w <= 0 or pixel_h <= 0 or pixel_w > 8192 or pixel_h > 8192:
        return None

    # --- Map format to Noesis constant ---
    if fmt in (0x0, 0x5, 0x6):
        texFmt = noesis.NOESISTEX_RGBA32
    elif fmt in (0x7, 0x8, 0xB, 0xC):
        texFmt = noesis.NOESISTEX_DXT1
    elif fmt in (0x9, 0xD):
        texFmt = noesis.NOESISTEX_DXT3
    elif fmt in (0x3, 0x4, 0xA, 0xE):
        texFmt = noesis.NOESISTEX_DXT5
    else:
        return None

    # --- Data source auto-detection ---
    if mipsCount == mipsInFile:
        # Read pixel data from TFH at the mip offset
        data_start = mip_offset
        data_end = mip_offset + mip_size
        if data_end > len(data):
            return None
        pixel_data = data[data_start:data_end]
    else:
        # Read from .tfd file at the mip offset
        tfd_path = rapi.getExtensionlessName(rapi.getInputName()) + ".tfd"
        try:
            tfd_raw = rapi.loadIntoByteArray(tfd_path)
        except:
            print("ERROR: Cannot open TFD: %s" % tfd_path)
            return None
        if mip_offset + mip_size > len(tfd_raw):
            return None
        pixel_data = tfd_raw[mip_offset:mip_offset + mip_size]

    return (pixel_w, pixel_h, texFmt, pixel_data, fmt, mipsCount, mipsInFile)


# ================================================================
# v2 fallback mechanism — handles edge cases
# ================================================================
def fallback_load(tfhPath):
    """Try to load texture using v2 guess_size fallback mechanism."""
    tfdFile = rapi.getExtensionlessName(tfhPath) + ".tfd"
    try:
        tfdRaw = rapi.loadIntoByteArray(tfdFile)
        tfdLen = len(tfdRaw)
    except:
        print("ERROR: Cannot open TFD for fallback: %s" % tfdFile)
        return None

    w, h, block = guess_size(tfdLen)
    if "sai" in tfdFile.lower():
        w = h = 4096
        block = 8

    mainSize = calc_mip(w, h, block)
    for off in [tfdLen - mainSize, 0]:
        if off >= 0 and off + mainSize <= tfdLen:
            break
    if mainSize > tfdLen:
        mainSize = tfdLen

    texFmt = noesis.NOESISTEX_DXT5 if block == 16 else noesis.NOESISTEX_DXT1
    pixel_data = tfdRaw[off:off + mainSize]
    print("[fallback] %dx%d %s off=%d" % (w, h, "DXT5" if block == 16 else "DXT1", off))
    return (w, h, texFmt, pixel_data)


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

    # === PHP-style mip table parsing (primary path) ===
    php_result = parse_tfh_php(data)
    if php_result is not None:
        w, h, texFmt, pixel_data, fmt, mipsCount, mipsInFile = php_result
        fmt_name = FMT_NAMES.get(fmt, "UNK")
        print("TFH: %dx%d fmt=0x%X(%s) mips=%d/%d" % (w, h, fmt, fmt_name, mipsCount, mipsInFile))
        # Data byte order: [B][G][R][A] -> Noesis RGBA32 expects [R][G][B][A]
        if texFmt == noesis.NOESISTEX_RGBA32:
            arr = bytearray(pixel_data)
            for i in range(0, len(arr), 4):
                arr[i], arr[i+2] = arr[i+2], arr[i]
            pixel_data = bytes(arr)
        texList.append(NoeTexture(tfhPath, w, h, pixel_data, texFmt))
        return 1

    # === Fallback mechanism ===
    print("[fallback] PHP parsing failed, using v2 TFD size estimation")
    fb_result = fallback_load(tfhPath)
    if fb_result is not None:
        w, h, texFmt, pixel_data = fb_result
        texList.append(NoeTexture(tfhPath, w, h, pixel_data, texFmt))
        return 1

    # === Last resort: raw data as square DXT5 ===
    print("[last-resort] reading raw TFD as square DXT5")
    tfdFile = rapi.getExtensionlessName(tfhPath) + ".tfd"
    try:
        tfdRaw = rapi.loadIntoByteArray(tfdFile)
        w = h = int(math.sqrt(len(tfdRaw)))
        if w > 0:
            texList.append(NoeTexture(tfhPath, w, h, tfdRaw, noesis.NOESISTEX_DXT5))
            return 1
    except:
        pass

    print("ERROR: Failed to load texture: %s" % tfhPath)
    return 0


# ================================================================
# Format name lookup (for debug printing)
# ================================================================
FMT_NAMES = {
    0x0: "RGBA",
    0x3: "DXT5",
    0x4: "DXT5",
    0x5: "RGBA",
    0x6: "RGBA",
    0x7: "DXT1",
    0x8: "DXT1",
    0x9: "DXT3",
    0xA: "DXT5",
    0xB: "DXT1",
    0xC: "DXT1",
    0xD: "DXT3",
    0xE: "DXT5",
}
