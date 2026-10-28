"""Read newc initramfs members and add the live UART workaround."""
import zlib
LIMIT = 768 * 1024 * 1024
PREFIX = b'''#!/bin/sh
# zero3-console: wait until modular UART dependencies have registered ttyS0.
mount -t devtmpfs devtmpfs /dev 2>/dev/null
[ -c /dev/kmsg ] || mknod /dev/kmsg c 1 11
exec </dev/null >/dev/kmsg 2>&1
'''
WAIT = b'''zero3_wait=0
while ! grep -qs '^ttyS0[[:space:]]' /proc/consoles; do
    sleep 1
    zero3_wait=$((zero3_wait + 1))
    [ "$zero3_wait" -lt 60 ] || break
done
if grep -qs '^ttyS0[[:space:]]' /proc/consoles; then
    exec </dev/ttyS0 >/dev/ttyS0 2>&1
fi
unset zero3_wait
'''

def member(name, mode, data, inode=1):
    filename = name.encode("utf-8") + b"\0"
    fields = [inode, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(filename), 0]
    blob = b"070701" + b"".join(f"{v:08x}".encode() for v in fields) + filename
    blob += bytes((-len(blob)) % 4)
    blob += data
    return blob + bytes((-len(blob)) % 4)

def entries(blob):
    consumed = 0
    while blob:
        blob = blob.lstrip(b"\0")
        if not blob:
            return
        if blob.startswith(b"\x1f\x8b"):
            dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
            unpacked = dec.decompress(blob, LIMIT + 1)
            if not dec.eof or len(unpacked) > LIMIT:
                raise ValueError("Truncated or oversized gzip initramfs")
            blob = unpacked + dec.unused_data
            continue
        if blob.startswith(b"\x28\xb5\x2f\xfd"):
            import zstandard
            dec = zstandard.ZstdDecompressor().decompressobj()
            unpacked = dec.decompress(blob)
            if not dec.eof or len(unpacked) > LIMIT:
                raise ValueError("Truncated or oversized zstd initramfs")
            blob = unpacked + dec.unused_data
            continue
        offset = 0
        while True:
            if blob[offset:offset + 6] not in (b"070701", b"070702"):
                raise ValueError("Unrecognized newc initramfs member")
            if offset + 110 > len(blob):
                raise ValueError("Truncated newc header")
            fields = [int(blob[offset + 6 + i * 8:offset + 14 + i * 8], 16) for i in range(13)]
            size, namesize = fields[6], fields[11]
            if namesize < 1 or size > LIMIT:
                raise ValueError("Invalid newc lengths")
            endname = offset + 110 + namesize
            start = (endname + 3) & ~3
            end = start + size
            if end > len(blob) or endname > len(blob) or blob[endname - 1] != 0:
                raise ValueError("Truncated newc member")
            name = blob[offset + 110:endname - 1].decode("utf-8")
            data = blob[start:end]
            offset = (end + 3) & ~3
            consumed += size
            if consumed > LIMIT:
                raise ValueError("Initramfs expansion limit exceeded")
            if name == "TRAILER!!!":
                blob = blob[offset:]
                break
            yield name.removeprefix("./"), fields, data

def console_overlay(blob):
    names = {}
    for name, _, content in entries(blob):
        if name in ("init", "scripts/functions", "usr/lib/dracut/modules.txt"):
            names[name] = content
    if "usr/lib/dracut/modules.txt" in names:
        return blob, "dracut-preserved"
    init = names.get("init", b"")
    marker = b"run_scripts /scripts/init-top\n"
    if b"# zero3-console:" in init:
        return blob, "already-patched"
    if "scripts/functions" not in names or marker not in init or not init.startswith(b"#!/"):
        raise ValueError("Unknown initramfs framework; refusing to replace /init")
    fixed = (PREFIX + init.split(b"\n", 1)[1]).replace(marker, marker + WAIT, 1)
    archive = member("init", 0o100755, fixed, 0x6001) + member("TRAILER!!!", 0, b"", 0x6002)
    archive += bytes((-len(archive)) % 512)
    import zstandard
    result = blob + zstandard.ZstdCompressor(level=3).compress(archive)
    return result, "initramfs-tools-uart-overlay"
