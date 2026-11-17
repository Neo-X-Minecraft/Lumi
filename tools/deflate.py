# SPDX-License-Identifier: 0BSD
"""Deterministic DEFLATE encoding from a checked LZ77/Huffman packing plan."""
import struct
import zlib

LBASE = (
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    13,
    15,
    17,
    19,
    23,
    27,
    31,
    35,
    43,
    51,
    59,
    67,
    83,
    99,
    115,
    131,
    163,
    195,
    227,
    258,
)
LEXTRA = (0,) * 8 + (1,) * 4 + (2,) * 4 + (3,) * 4 + (4,) * 4 + (5,) * 4 + (0,)
DBASE = (
    1,
    2,
    3,
    4,
    5,
    7,
    9,
    13,
    17,
    25,
    33,
    49,
    65,
    97,
    129,
    193,
    257,
    385,
    513,
    769,
    1025,
    1537,
    2049,
    3073,
    4097,
    6145,
    8193,
    12289,
    16385,
    24577,
)
DEXTRA = (0, 0, 0, 0) + tuple(v for n in range(1, 14) for v in (n, n))
CLORDER = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15)


class BitsIn:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def read(self, n):
        if self.pos + n > len(self.data) * 8:
            raise ValueError("Truncated DEFLATE data")
        value = 0
        for bit in range(n):
            value |= ((self.data[self.pos // 8] >> (self.pos % 8)) & 1) << bit
            self.pos += 1
        return value


class BitsOut:
    def __init__(self):
        self.data, self.word, self.count = bytearray(), 0, 0

    def write(self, value, n):
        if not 0 <= value < 1 << n:
            raise ValueError("Bit field is out of range")
        self.word |= value << self.count
        self.count += n
        while self.count >= 8:
            self.data.append(self.word & 255)
            self.word >>= 8
            self.count -= 8

    def finish(self):
        if self.count:
            self.data.append(self.word & 255)
        return bytes(self.data)


def codes(lengths):
    counts = [0] * 16
    for n in lengths:
        if not 0 <= n <= 15:
            raise ValueError("Invalid Huffman code length")
        if n:
            counts[n] += 1
    current, next_code = 0, [0] * 16
    for n in range(1, 16):
        current = (current + counts[n - 1]) << 1
        if current + counts[n] > 1 << n:
            raise ValueError("Oversubscribed Huffman tree")
        next_code[n] = current
    result = {}
    for symbol, n in enumerate(lengths):
        if n:
            c = next_code[n]
            reverse = int(f"{c:0{n}b}"[::-1], 2)
            result[symbol] = (reverse, n)
            next_code[n] += 1
    return result


def read_symbol(reader, table):
    inverse = {(c, n): symbol for symbol, (c, n) in table.items()}
    word = 0
    for n in range(1, 16):
        word |= reader.read(1) << (n - 1)
        if (word, n) in inverse:
            return inverse[word, n]
    raise ValueError("Invalid Huffman symbol")


def expand_tree(runs):
    values = []
    for item in runs:
        if isinstance(item, int):
            if not 0 <= item <= 15:
                raise ValueError("Invalid code length")
            values.append(item)
        else:
            symbol, count = item
            if symbol == 16 and values and 3 <= count <= 6:
                values.extend([values[-1]] * count)
            elif symbol == 17 and 3 <= count <= 10:
                values.extend([0] * count)
            elif symbol == 18 and 11 <= count <= 138:
                values.extend([0] * count)
            else:
                raise ValueError("Invalid code-length run")
    return values


def tables(block):
    if block["type"] == 1:
        return codes([8] * 144 + [9] * 112 + [7] * 24 + [8] * 8), codes([5] * 32)
    lengths = expand_tree(block["tree_runs"])
    if len(lengths) != block["hlit"] + block["hdist"]:
        raise ValueError("Huffman alphabet size does not match its plan")
    return codes(lengths[: block["hlit"]]), codes(lengths[block["hlit"] :])


def extract(stream):
    """Extract a transparent packing plan; literal pixel values stay in the artwork."""
    if (
        len(stream) < 6
        or (stream[0] * 256 + stream[1]) % 31
        or stream[0] & 15 != 8
        or stream[1] & 32
    ):
        raise ValueError("Expected a zlib stream without a preset dictionary")
    reader = BitsIn(stream[2:-4])
    output, blocks = bytearray(), []
    while True:
        final, kind = reader.read(1), reader.read(2)
        block = {"final": bool(final), "type": kind}
        if kind == 0:
            n = (-reader.pos) % 8
            block["alignment"] = [reader.read(n), n]
            length, check = reader.read(16), reader.read(16)
            if length ^ check != 65535:
                raise ValueError("Invalid stored-block length")
            block["length"] = length
            output.extend(reader.read(8) for _ in range(length))
        elif kind in (1, 2):
            if kind == 2:
                hlit, hdist, hclen = (
                    reader.read(5) + 257,
                    reader.read(5) + 1,
                    reader.read(4) + 4,
                )
                cl = [reader.read(3) for _ in range(hclen)]
                lengths = [0] * 19
                for symbol, n in zip(CLORDER, cl):
                    lengths[symbol] = n
                table, runs, expanded = codes(lengths), [], []
                while len(expanded) < hlit + hdist:
                    symbol = read_symbol(reader, table)
                    if symbol <= 15:
                        runs.append(symbol)
                    else:
                        extra, base = {16: (2, 3), 17: (3, 3), 18: (7, 11)}[symbol]
                        runs.append([symbol, reader.read(extra) + base])
                    expanded = expand_tree(runs)
                block.update(hlit=hlit, hdist=hdist, code_lengths=cl, tree_runs=runs)
            literal, distance = tables(block)
            tokens = []
            while True:
                symbol = read_symbol(reader, literal)
                if symbol < 256:
                    output.append(symbol)
                    if tokens and isinstance(tokens[-1], int):
                        tokens[-1] += 1
                    else:
                        tokens.append(1)
                elif symbol == 256:
                    break
                elif 257 <= symbol <= 285:
                    k = symbol - 257
                    length = LBASE[k] + reader.read(LEXTRA[k])
                    code = read_symbol(reader, distance)
                    if code >= len(DBASE):
                        raise ValueError("Invalid match distance")
                    offset = DBASE[code] + reader.read(DEXTRA[code])
                    if offset > len(output):
                        raise ValueError("Match precedes the pixel stream")
                    for _ in range(length):
                        output.append(output[-offset])
                    tokens.append([length, offset, symbol])
                else:
                    raise ValueError("Invalid match length")
            block["tokens"] = tokens
        else:
            raise ValueError("Reserved DEFLATE block type")
        blocks.append(block)
        if final:
            break
    n = len(reader.data) * 8 - reader.pos
    if n > 7:
        raise ValueError("Unexpected bytes after DEFLATE blocks")
    plan = {
        "format": 1,
        "zlib_header": stream[:2].hex(),
        "blocks": blocks,
        "tail": [reader.read(n), n],
    }
    if bytes(output) != zlib.decompress(stream):
        raise ValueError("Decoded pixels do not match zlib")
    return plan, bytes(output)


def encode(raw, plan):
    """Encode supplied pixel bytes using the checked match layout and Huffman trees."""
    writer, pos = BitsOut(), 0
    for index, block in enumerate(plan["blocks"]):
        if bool(block["final"]) != (index == len(plan["blocks"]) - 1):
            raise ValueError("Invalid final-block flag")
        writer.write(int(block["final"]), 1)
        kind = block["type"]
        writer.write(kind, 2)
        if kind == 0:
            writer.write(*block["alignment"])
            n = block["length"]
            writer.write(n, 16)
            writer.write(n ^ 65535, 16)
            if pos + n > len(raw):
                raise ValueError("Stored block exceeds artwork")
            for value in raw[pos : pos + n]:
                writer.write(value, 8)
            pos += n
            continue
        if kind == 2:
            writer.write(block["hlit"] - 257, 5)
            writer.write(block["hdist"] - 1, 5)
            writer.write(len(block["code_lengths"]) - 4, 4)
            lengths = [0] * 19
            for symbol, n in zip(CLORDER, block["code_lengths"]):
                writer.write(n, 3)
                lengths[symbol] = n
            table = codes(lengths)
            for item in block["tree_runs"]:
                symbol = item if isinstance(item, int) else item[0]
                writer.write(*table[symbol])
                if symbol >= 16:
                    extra, base = {16: (2, 3), 17: (3, 3), 18: (7, 11)}[symbol]
                    writer.write(item[1] - base, extra)
        literal, distance = tables(block)
        for token in block["tokens"]:
            if isinstance(token, int):
                if pos + token > len(raw):
                    raise ValueError("Literal run exceeds artwork")
                for value in raw[pos : pos + token]:
                    if value not in literal:
                        raise ValueError("Artwork needs a different Huffman tree")
                    writer.write(*literal[value])
                pos += token
            else:
                length, offset, symbol = token
                if offset > pos or pos + length > len(raw):
                    raise ValueError("Match exceeds artwork")
                if any(raw[pos + i] != raw[pos + i - offset] for i in range(length)):
                    raise ValueError("Artwork does not match the compression plan")
                k = symbol - 257
                writer.write(*literal[symbol])
                writer.write(length - LBASE[k], LEXTRA[k])
                code = max(i for i, base in enumerate(DBASE) if base <= offset)
                writer.write(*distance[code])
                writer.write(offset - DBASE[code], DEXTRA[code])
                pos += length
        writer.write(*literal[256])
    if pos != len(raw):
        raise ValueError("Compression plan did not consume the artwork")
    writer.write(*plan["tail"])
    stream = (
        bytes.fromhex(plan["zlib_header"])
        + writer.finish()
        + struct.pack("!I", zlib.adler32(raw) & 0xFFFFFFFF)
    )
    if zlib.decompress(stream) != raw:
        raise ValueError("Compressed pixels failed validation")
    return stream
