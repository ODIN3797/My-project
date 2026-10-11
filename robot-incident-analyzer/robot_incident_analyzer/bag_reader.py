"""Streaming bag readers: rosbag2 SQLite, MCAP (including common chunk encodings).

Rosbags, when locally installed, is attempted first for full ROS2 bag directories.
A small native reader handles standalone .db3 and .mcap without ROS installed.
"""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import sqlite3
import struct
import zlib
from typing import Iterator
from urllib.parse import quote

MAGIC = b'\x89MCAP0\r\n'
MAX_RECORD = 256 * 1024 * 1024  # refuse untrusted oversized decompression


def iter_db3(path: Path) -> Iterator[tuple[str, str, int, bytes]]:
    uri = 'file:' + quote(str(path.resolve()), safe='/') + '?mode=ro'
    con = sqlite3.connect(uri, uri=True)
    try:
        topics = {int(tid):(name,typ) for tid,name,typ in con.execute('SELECT id,name,type FROM topics')}
        for ns,tid,raw in con.execute('SELECT timestamp,topic_id,data FROM messages ORDER BY timestamp'):
            if tid in topics:
                name,typ = topics[tid]
                yield name,typ,int(ns),raw
    except sqlite3.DatabaseError as exc:
        raise ValueError(f'Invalid SQLite rosbag2 file {path}: {exc}') from exc
    finally:
        con.close()


class Buffer:
    def __init__(self, data: bytes):
        self.data, self.pos = data, 0
    def take(self, n: int) -> bytes:
        if n < 0 or self.pos+n > len(self.data):
            raise ValueError('Malformed MCAP record')
        out = self.data[self.pos:self.pos+n]
        self.pos += n
        return out
    def u16(self): return struct.unpack('<H',self.take(2))[0]
    def u32(self): return struct.unpack('<I',self.take(4))[0]
    def u64(self): return struct.unpack('<Q',self.take(8))[0]
    def text(self):
        length=self.u32()
        if length>65536: raise ValueError('Unreasonably long MCAP field')
        return self.take(length).decode('utf-8',errors='replace')
    def blob(self):
        size=self.u32()
        if size > MAX_RECORD: raise ValueError('Oversized MCAP field')
        return self.take(size)


def iterate_records(stream) -> Iterator[tuple[int,bytes]]:
    while True:
        head=stream.read(9)
        if not head: break
        # A valid MCAP file ends with the 8-byte magic marker after Footer.
        if head.startswith(MAGIC):
            break
        if len(head)!=9:
            raise ValueError('Truncated MCAP record header')
        opcode=head[0]
        length=struct.unpack('<Q',head[1:])[0]
        if length>MAX_RECORD:
            raise ValueError('MCAP record exceeds 256 MiB safety bound')
        data=stream.read(length)
        if len(data)!=length: raise ValueError('Truncated MCAP record body')
        yield opcode,data
        if opcode==0x02:  # footer
            break


def unpack_chunk(data: bytes, warnings: list[str]):
    b=Buffer(data)
    b.u64(); b.u64(); uncompressed_size=b.u64(); uncompressed_crc=b.u32()
    compression=b.text()
    records=b.take(b.u64())
    if uncompressed_size>MAX_RECORD:
        warnings.append('MCAP chunk too large; skipped')
        return None
    if compression in ('', 'none'):
        payload=records
    elif compression=='zstd':
        try:
            import zstandard as zstd
        except ImportError:
            try:
                from .zstd_native import decompress_zstd
                payload = decompress_zstd(records, uncompressed_size)
            except ImportError:
                warnings.append('MCAP zstd chunk skipped; install zstandard or system libzstd to read it')
                return None
        else:
            payload=zstd.ZstdDecompressor().decompress(records,max_output_size=MAX_RECORD)
    elif compression=='lz4':
        try:
            import lz4.frame
        except ImportError:
            warnings.append('MCAP lz4 chunk skipped; install lz4 to read it')
            return None
        payload=lz4.frame.decompress(records)
    else:
        warnings.append(f'Unsupported MCAP chunk compression {compression!r}; skipped')
        return None
    if len(payload)>MAX_RECORD or len(payload)!=uncompressed_size:
        raise ValueError('MCAP decompression size mismatch')
    if uncompressed_crc and zlib.crc32(payload) != uncompressed_crc:
        raise ValueError('MCAP chunk CRC mismatch: recording may be corrupted')
    return payload


def iter_mcap(path: Path, warnings: list[str]) -> Iterator[tuple[str,str,int,bytes]]:
    schemas: dict[int,str] = {}
    channels: dict[int,tuple[str,str,str]] = {}
    def consume(records):
        for opcode,data in records:
            b=Buffer(data)
            if opcode==0x03:  # Schema
                key=b.u16(); name=b.text(); b.text(); b.blob()
                schemas[key]=name
            elif opcode==0x04:  # Channel
                channel_id=b.u16(); schema_id=b.u16(); topic=b.text(); encoding=b.text()
                channels[channel_id]=(topic,schemas.get(schema_id, ''),encoding)
            elif opcode==0x05:  # Message
                channel_id=b.u16(); b.u32(); log_ns=b.u64(); b.u64()
                if channel_id not in channels: continue
                topic,typ,encoding=channels[channel_id]
                if encoding!='cdr':
                    warnings.append(f'{topic}: message encoding {encoding!r} not supported (only cdr)')
                    continue
                yield topic,typ,log_ns,b.take(len(data)-b.pos)
            elif opcode==0x06:  # Chunk
                payload=unpack_chunk(data,warnings)
                if payload is not None:
                    yield from consume(iterate_records(BytesIO(payload)))
    with path.open('rb') as fp:
        if fp.read(8)!=MAGIC:
            raise ValueError(f'Not a valid MCAP file: {path}')
        # Footer plus trailing magic are both mandatory in a complete MCAP.
        # A missing trailer must not produce an apparently successful report.
        yield from consume(iterate_records(fp))
        if fp.read(8) != MAGIC:
            raise ValueError('MCAP footer/trailing magic missing or file truncated')
        if fp.read(1):
            raise ValueError('Unexpected data after MCAP trailing magic')


def iter_rosbags(path: Path):
    """Optional integration for complete ROS2 bags; file paths fallback to native."""
    from rosbags.highlevel import AnyReader
    with AnyReader([path]) as reader:
        for connection,timestamp,raw in reader.messages():
            yield connection.topic,connection.msgtype,int(timestamp),raw


def read_bag(path: Path, max_messages: int, warnings: list[str]):
    """Stream messages; optional rosbags first for MCAP when installed.

    A failing rosbags reader falls back to the native reader only if no records
    have been yielded yet, to prevent silent duplicate data.
    """
    if path.suffix.lower()=='.mcap':
        try:
            from rosbags.highlevel import AnyReader  # noqa: F401
        except ImportError:
            pass
        else:
            candidate = iter_rosbags(path)
            try:
                first = next(candidate)
            except StopIteration:
                pass
            except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
                warnings.append(f'rosbags unavailable for {path.name}; native MCAP reader used: {str(exc)[:120]}')
            else:
                yield first
                # The first item consumes one place in the maximum message budget.
                yield from _limited(candidate, max_messages-1, warnings)
                return
    if path.suffix.lower() in ('.db3','.sqlite3'):
        iterator = iter_db3(path)
    elif path.suffix.lower()=='.mcap':
        iterator = iter_mcap(path,warnings)
    else:
        raise ValueError(f'Unsupported bag storage for {path}')
    yield from _limited(iterator,max_messages,warnings)


def _limited(iterator,max_messages,warnings):
    for idx,record in enumerate(iterator):
        if idx>=max_messages:
            warnings.append(f'Only first {max_messages:,} messages processed; topic statistics are partial.')
            break
        yield record
