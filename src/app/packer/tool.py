# src/app/packer/tool.py

import sys
from pathlib import Path

packer_entry_usage = "usage: tool.py input.asc output.bin\n"
packer_entry_fail = "failed: {}\n"


class AppPackerImage:
    def __init__(self):
        self.device = None
        self.warmboot = "enabled"
        self.initblop = bytearray()
        self.cram = []
        self.bram = []


class AppPacker:
    packer_device = "1k"
    packer_cram_w = 332
    packer_cram_h = 144
    packer_bram_w = 64
    packer_bram_h = 256
    packer_bram_chunk = 128
    packer_chip_w = 12
    packer_chip_h = 16
    packer_banks = 4
    packer_cols = (18, 54, 54, 42, 54, 54, 54)
    packer_ram_x = (3, 10)
    packer_kind_corner = "corner"
    packer_kind_logic = "logic"
    packer_kind_ramb = "ramb"
    packer_kind_ramt = "ramt"
    packer_kind_io = "io"
    packer_tile_w = {
        packer_kind_corner: 0,
        packer_kind_logic: 54,
        packer_kind_ramb: 42,
        packer_kind_ramt: 42,
        packer_kind_io: 18,
    }
    packer_cmd_io_tile = ".io_tile"
    packer_cmd_logic_tile = ".logic_tile"
    packer_cmd_ramb_tile = ".ramb_tile"
    packer_cmd_ramt_tile = ".ramt_tile"
    packer_cmd_comment_name = ".comment"
    packer_cmd_device_name = ".device"
    packer_cmd_warmboot_name = ".warmboot"
    packer_cmd_ram_name = ".ram_data"
    packer_cmd_extra_name = ".extra_bit"
    packer_cmd_sym_name = ".sym"
    packer_tile_cmds = {
        packer_cmd_io_tile: packer_kind_io,
        packer_cmd_logic_tile: packer_kind_logic,
        packer_cmd_ramb_tile: packer_kind_ramb,
        packer_cmd_ramt_tile: packer_kind_ramt,
    }
    packer_wb_on = "enabled"
    packer_wb_off = "disabled"
    packer_key_kind = "kind"
    packer_key_bank = "bank"
    packer_key_right = "right"
    packer_key_top = "top"
    packer_key_side = "side"
    packer_key_xoff = "xoff"
    packer_key_yoff = "yoff"
    packer_key_colw = "colw"
    packer_key_off = "off"
    packer_dot = "."
    packer_one = "1"
    packer_nl = "\n"
    packer_empty = ""
    packer_enc = "utf-8"
    packer_order = "big"
    packer_perm_x = (
        23, 25, 26, 27, 16, 17, 18, 19, 20,
        14, 32, 33, 34, 35, 36, 37, 4, 5,
    )
    packer_perm_y = (
        0, 1, 3, 2, 4, 5, 7, 6, 8, 9, 11, 10, 12, 13, 15, 14,
    )
    packer_preamble = bytes([0x7E, 0xAA, 0x99, 0x7E])
    packer_freq_codes = (0x00, 0x01, 0x02)
    packer_crc_poly = 0x1021
    packer_crc_init = 0xFFFF
    packer_bit_table = bytes.maketrans(b"\x00\x01", b"01")
    packer_err_freq = "unknown freqrange {}"
    packer_err_bits = "bit count not a multiple of 8"
    packer_err_device_first = "missing .device before "
    packer_err_arg = "bad argument for "
    packer_err_tile_x = "tile x out of range: {}"
    packer_err_tile_y = "tile y out of range: {}"
    packer_err_tile_kind = "got {} for {} tile {} {}"
    packer_err_cram_x = "cram x out of range: {}"
    packer_err_cram_y = "cram y out of range: {}"
    packer_err_bram_x = "bram x out of range: {}"
    packer_err_bram_y = "bram y out of range: {}"
    packer_err_hex = "not a hex digit '{}' in line '{}'"
    packer_err_device_twice = "more than one .device statement"
    packer_err_chip = "unsupported chip '{}'"
    packer_err_warmboot = "unknown warmboot '{}'"
    packer_err_extra_bank = "extra bit bank out of range"
    packer_err_statement = "unknown statement: "
    packer_err_data = "unexpected data line: "
    packer_err_no_device = "no .device statement found"

    def __init__(self, freq=0, nosleep=False):
        if freq not in range(len(self.packer_freq_codes)):
            raise ValueError(self.packer_err_freq.format(freq))
        self.packer_freq = freq
        self.packer_nosleep = nosleep
        self.packer_table = self.packer_make_table()

    def packer_make_table(self):
        table = []
        for byte in range(256):
            crc = byte << 8
            for _ in range(8):
                crc <<= 1
                if crc & 0x10000:
                    crc ^= 0x10000 | self.packer_crc_poly
            table.append(crc & 0xFFFF)
        return table

    def packer_crc(self, crc, data):
        for byte in data:
            key = (crc >> 8) ^ byte
            crc = ((crc << 8) & 0xFFFF) ^ self.packer_table[key]
        return crc

    def packer_set(self, op, value):
        return bytes([op, (value >> 8) & 0xFF, value & 0xFF])

    def packer_bits_bytes(self, bits):
        if len(bits) % 8:
            raise ValueError(self.packer_err_bits)
        text = bytes(bits).translate(self.packer_bit_table)
        return int(text, 2).to_bytes(len(bits) // 8, self.packer_order)

    def packer_block(self, kind, bits):
        head = bytes([0x01, kind])
        data = self.packer_bits_bytes(bits)
        return head + data + bytes([0x00, 0x00])

    def packer_bank_select(self, bank):
        return bytes([0x11, bank])

    def packer_body_cram(self, img):
        body = bytearray()
        body += self.packer_set(0x62, self.packer_cram_w - 1)
        body += self.packer_set(0x72, self.packer_cram_h)
        body += self.packer_set(0x82, 0)
        for bank in range(self.packer_banks):
            body += self.packer_bank_select(bank)
            body += self.packer_block(0x01, img.cram[bank])
        return body

    def packer_body_bram(self, img):
        body = bytearray()
        width = self.packer_bram_w
        chunk = self.packer_bram_chunk
        body += self.packer_set(0x62, width - 1)
        body += self.packer_set(0x72, chunk)
        for bank in range(self.packer_banks):
            body += self.packer_bank_select(bank)
            for off in range(0, self.packer_bram_h, chunk):
                first = off * width
                bits = img.bram[bank][first:first + chunk * width]
                body += self.packer_set(0x82, off)
                body += self.packer_block(0x03, bits)
        return body

    def packer_flags(self, img):
        flag = 0x20 if img.warmboot == self.packer_wb_on else 0x00
        return flag | (0x01 if self.packer_nosleep else 0x00)

    def packer_body(self, img):
        body = bytearray([0x92, 0x00, self.packer_flags(img)])
        body += self.packer_body_cram(img)
        body += self.packer_body_bram(img)
        body.append(0x22)
        return body

    def packer_head(self, img):
        head = bytearray(img.initblop)
        head += self.packer_preamble
        code = self.packer_freq_codes[self.packer_freq]
        head += bytes([0x51, code])
        head += bytes([0x01, 0x05])
        return head

    def packer_encode(self, img):
        body = self.packer_body(img)
        crc = self.packer_crc(self.packer_crc_init, body)
        tail = bytes([crc >> 8, crc & 0xFF, 0x01, 0x06, 0x00])
        return bytes(self.packer_head(img) + body + tail)

    def packer_need(self, img, name):
        if img.device is None:
            raise ValueError(self.packer_err_device_first + name)

    def packer_int(self, words, at, name):
        try:
            return int(words[at])
        except (IndexError, ValueError):
            raise ValueError(self.packer_err_arg + name)

    def packer_tile_type(self, x, y):
        wide = self.packer_chip_w + 1
        high = self.packer_chip_h + 1
        edge_x = x in (0, wide)
        edge_y = y in (0, high)
        if edge_x and edge_y:
            return self.packer_kind_corner
        if edge_x or edge_y:
            return self.packer_kind_io
        if x in self.packer_ram_x:
            if y % 2 == 1:
                return self.packer_kind_ramb
            return self.packer_kind_ramt
        return self.packer_kind_logic

    def packer_tile_check(self, x, y, name):
        if not (0 <= x <= self.packer_chip_w + 1):
            raise ValueError(self.packer_err_tile_x.format(x))
        if not (0 <= y <= self.packer_chip_h + 1):
            raise ValueError(self.packer_err_tile_y.format(y))
        kind = self.packer_tile_type(x, y)
        if self.packer_tile_cmds.get(name) != kind:
            raise ValueError(
                self.packer_err_tile_kind.format(name, kind, x, y)
            )
        return kind

    def packer_geo(self, kind, x, y):
        wide = self.packer_chip_w
        high = self.packer_chip_h
        right = x > wide // 2
        top = y > high // 2
        tx = wide + 1 - x if right else x
        ty = high + 1 - y if top else y
        return {
            self.packer_key_kind: kind,
            self.packer_key_bank: (1 if top else 0) | (2 if right else 0),
            self.packer_key_right: right,
            self.packer_key_top: top,
            self.packer_key_side: x == 0 or x == wide + 1,
            self.packer_key_xoff: sum(self.packer_cols[:tx]),
            self.packer_key_yoff: 16 * ty,
            self.packer_key_colw: self.packer_cols[tx],
        }

    def packer_cram_xy(self, geo, bit_x, bit_y):
        base_x = geo[self.packer_key_xoff]
        base_y = geo[self.packer_key_yoff]
        last = geo[self.packer_key_colw] - 1
        right = geo[self.packer_key_right]
        top = geo[self.packer_key_top]
        kind = geo[self.packer_key_kind]
        side = geo[self.packer_key_side]
        is_io = kind == self.packer_kind_io
        if is_io and not side:
            cy = base_y + 15 - self.packer_perm_y[bit_y]
            px = self.packer_perm_x[bit_x]
            cx = base_x + last - px if right else base_x + px
            return cx, cy
        mirror = right or (is_io and side)
        cx = base_x + last - bit_x if mirror else base_x + bit_x
        cy = base_y + 15 - bit_y if top else base_y + bit_y
        return cx, cy

    def packer_cram_set(self, img, geo, bit_x, bit_y):
        cx, cy = self.packer_cram_xy(geo, bit_x, bit_y)
        self.packer_cram_put(img, geo[self.packer_key_bank], cx, cy)

    def packer_cram_put(self, img, bank, cx, cy):
        if not (0 <= cx < self.packer_cram_w):
            raise ValueError(self.packer_err_cram_x.format(cx))
        if not (0 <= cy < self.packer_cram_h):
            raise ValueError(self.packer_err_cram_y.format(cy))
        img.cram[bank][cy * self.packer_cram_w + cx] = 1

    def packer_bram_geo(self, x, y):
        wide = self.packer_chip_w
        high = self.packer_chip_h
        right = x > wide // 2
        top = y > high // 2
        skew = y - high // 2 if top else y - 1
        return {
            self.packer_key_bank: (1 if top else 0) | (2 if right else 0),
            self.packer_key_off: 16 * (skew // 2),
        }

    def packer_bram_put(self, img, geo, bit_x, bit_y):
        index = 256 * bit_y + (16 * (bit_x // 16) + 15 - bit_x % 16)
        bx = geo[self.packer_key_off] + index % 16
        by = index // 16
        if not (0 <= bx < self.packer_bram_w):
            raise ValueError(self.packer_err_bram_x.format(bx))
        if not (0 <= by < self.packer_bram_h):
            raise ValueError(self.packer_err_bram_y.format(by))
        bank = geo[self.packer_key_bank]
        img.bram[bank][by * self.packer_bram_w + bx] = 1

    def packer_rows(self, lines, at):
        rows = []
        while len(rows) < 16 and at < len(lines):
            if lines[at].startswith(self.packer_dot):
                break
            rows.append(lines[at])
            at += 1
        return rows, at

    def packer_cmd_comment(self, img, words, lines, at):
        blop = bytearray([0xFF, 0x00])
        while at < len(lines):
            if lines[at].startswith(self.packer_dot):
                break
            blop += lines[at].encode(self.packer_enc) + b"\x00"
            at += 1
        blop += bytes([0x00, 0xFF])
        img.initblop = blop
        return at

    def packer_cmd_device(self, img, words, lines, at):
        if img.device is not None:
            raise ValueError(self.packer_err_device_twice)
        name = words[1] if len(words) > 1 else self.packer_empty
        if name != self.packer_device:
            raise ValueError(self.packer_err_chip.format(name))
        size = self.packer_cram_w * self.packer_cram_h
        bsize = self.packer_bram_w * self.packer_bram_h
        img.device = name
        img.cram = [bytearray(size) for _ in range(4)]
        img.bram = [bytearray(bsize) for _ in range(4)]
        return at

    def packer_cmd_warmboot(self, img, words, lines, at):
        mode = words[1] if len(words) > 1 else self.packer_empty
        if mode not in (self.packer_wb_off, self.packer_wb_on):
            raise ValueError(self.packer_err_warmboot.format(mode))
        img.warmboot = mode
        return at

    def packer_cmd_tile(self, img, words, lines, at):
        name = words[0]
        self.packer_need(img, name)
        x = self.packer_int(words, 1, name)
        y = self.packer_int(words, 2, name)
        kind = self.packer_tile_check(x, y, name)
        geo = self.packer_geo(kind, x, y)
        width = self.packer_tile_w[kind]
        rows, at = self.packer_rows(lines, at)
        for bit_y, row in enumerate(rows):
            for bit_x, ch in enumerate(row[:width]):
                if ch == self.packer_one:
                    self.packer_cram_set(img, geo, bit_x, bit_y)
        return at

    def packer_hex(self, ch, row):
        try:
            return int(ch, 16)
        except ValueError:
            raise ValueError(self.packer_err_hex.format(ch, row))

    def packer_ram_row(self, img, geo, bit_y, row):
        bit_x = 256 - 4
        for ch in row:
            if bit_x < 0:
                break
            value = self.packer_hex(ch, row)
            for i in range(4):
                if value & (1 << i):
                    self.packer_bram_put(img, geo, bit_x + i, bit_y)
            bit_x -= 4

    def packer_cmd_ram(self, img, words, lines, at):
        name = words[0]
        self.packer_need(img, name)
        x = self.packer_int(words, 1, name)
        y = self.packer_int(words, 2, name)
        geo = self.packer_bram_geo(x, y)
        rows, at = self.packer_rows(lines, at)
        for bit_y, row in enumerate(rows):
            self.packer_ram_row(img, geo, bit_y, row)
        return at

    def packer_cmd_extra(self, img, words, lines, at):
        name = words[0]
        self.packer_need(img, name)
        bank = self.packer_int(words, 1, name)
        cx = self.packer_int(words, 2, name)
        cy = self.packer_int(words, 3, name)
        if not (0 <= bank < self.packer_banks):
            raise ValueError(self.packer_err_extra_bank)
        self.packer_cram_put(img, bank, cx, cy)
        return at

    def packer_cmd_skip(self, img, words, lines, at):
        return at

    def packer_handlers(self):
        table = {
            self.packer_cmd_comment_name: self.packer_cmd_comment,
            self.packer_cmd_device_name: self.packer_cmd_device,
            self.packer_cmd_warmboot_name: self.packer_cmd_warmboot,
            self.packer_cmd_ram_name: self.packer_cmd_ram,
            self.packer_cmd_extra_name: self.packer_cmd_extra,
            self.packer_cmd_sym_name: self.packer_cmd_skip,
        }
        for name in self.packer_tile_cmds:
            table[name] = self.packer_cmd_tile
        return table

    def packer_dispatch(self, handlers, img, words, lines, at, line):
        handler = handlers.get(words[0])
        if handler is not None:
            return handler(img, words, lines, at)
        if words[0].startswith(self.packer_dot):
            raise ValueError(self.packer_err_statement + words[0])
        raise ValueError(self.packer_err_data + line)

    def packer_lines(self, text):
        lines = text.split(self.packer_nl)
        if lines and lines[-1] == self.packer_empty:
            lines.pop()
        return lines

    def packer_parse(self, text):
        img = AppPackerImage()
        handlers = self.packer_handlers()
        lines = self.packer_lines(text)
        at = 0
        while at < len(lines):
            line = lines[at]
            at += 1
            words = line.split()
            if words:
                at = self.packer_dispatch(
                    handlers, img, words, lines, at, line
                )
        if img.device is None:
            raise ValueError(self.packer_err_no_device)
        return img

    def packer_pack(self, text):
        return self.packer_encode(self.packer_parse(text))

    def packer_file(self, src, dst):
        data = self.packer_pack(Path(src).read_text())
        Path(dst).write_bytes(data)
        return len(data)


def packer_entry(argv):
    if len(argv) != 3:
        sys.stderr.write(packer_entry_usage)
        return 2
    try:
        AppPacker().packer_file(argv[1], argv[2])
    except (ValueError, OSError) as e:
        sys.stderr.write(packer_entry_fail.format(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(packer_entry(sys.argv))