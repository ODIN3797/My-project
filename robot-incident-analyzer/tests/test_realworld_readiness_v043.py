"""Independent MCAP container/codec integrity checks using synthetic CDR bytes.

These are *not* physical-robot datasets and cannot establish field accuracy.
"""
import ctypes
import ctypes.util
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from robot_incident_analyzer.bag_reader import MAGIC, iter_mcap
from robot_incident_analyzer.fixture_v2 import (
    field, make_mcap, mcap_record, message_records
)
from robot_incident_analyzer.field_validation import analyze_field_cases


def compress_native(data):
    name=ctypes.util.find_library('zstd')
    if not name:
        raise unittest.SkipTest('system libzstd not installed')
    lib=ctypes.CDLL(name)
    lib.ZSTD_compressBound.argtypes=[ctypes.c_size_t]
    lib.ZSTD_compressBound.restype=ctypes.c_size_t
    lib.ZSTD_compress.argtypes=[ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    lib.ZSTD_compress.restype=ctypes.c_size_t
    lib.ZSTD_isError.argtypes=[ctypes.c_size_t]
    lib.ZSTD_isError.restype=ctypes.c_uint
    cap=lib.ZSTD_compressBound(len(data))
    out=ctypes.create_string_buffer(cap)
    inp=ctypes.create_string_buffer(data)
    n=lib.ZSTD_compress(out,cap,inp,len(data),3)
    if lib.ZSTD_isError(n): raise RuntimeError('libzstd compress failed')
    return out.raw[:n]


def make_chunked(path, compression='zstd', bad_crc=False):
    # Build an independent, normally structured MCAP with top-level schemas and
    # channels and one zstd-compressed Chunk containing the messages.
    records=message_records()
    types=sorted({(topic,typ) for topic,typ,_,_ in records})
    ids={pair:i+1 for i,pair in enumerate(types)}
    header=mcap_record(1,field('ros2')+field('external-style-test'))
    metadata=[]
    for pair,ch in ids.items():
        topic,typ=pair
        metadata.append(mcap_record(3,struct.pack('<H',ch)+field(typ)+field('ros2msg')+struct.pack('<I',0)))
        metadata.append(mcap_record(4,struct.pack('<HH',ch,ch)+field(topic)+field('cdr')+struct.pack('<I',0)))
    inner=b''.join(mcap_record(5,struct.pack('<HIQQ',ids[(topic,typ)],i,ts,ts)+raw)
                   for i,(topic,typ,ts,raw) in enumerate(records))
    payload=compress_native(inner) if compression=='zstd' else inner
    crc=zlib.crc32(inner)
    if bad_crc: crc=(crc+1)%2**32
    chunk=struct.pack('<QQQI',min(x[2] for x in records),max(x[2] for x in records),len(inner),crc)
    chunk+=field(compression if compression!='none' else '')+struct.pack('<Q',len(payload))+payload
    all_records=[header,*metadata,mcap_record(6,chunk),mcap_record(15,struct.pack('<I',0)),
                 mcap_record(2,struct.pack('<QQI',0,0,0))]
    path.write_bytes(MAGIC+b''.join(all_records)+MAGIC)
    return path,len(records)


class McapFieldReadinessTests(unittest.TestCase):
    def test_system_zstd_decompression_without_pip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'compressed.mcap'
            _,expect=make_chunked(p)
            warnings=[]
            data=list(iter_mcap(p,warnings))
            self.assertEqual(len(data),expect)
            self.assertFalse(warnings)
            self.assertIn('/cmd_vel', {item[0] for item in data})
            out=analyze_field_cases([p],Path(d)/'out',origin='synthetic')
            case=out['cases'][0]
            self.assertEqual(case['message_count'],expect)
            self.assertGreater(case['event_count'],0)
            self.assertTrue((Path(d)/'out/case_01/report.html').exists())
            self.assertFalse(out['ground_truth_validated'])

    def test_compressed_chunk_crc_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'broken_crc.mcap'
            make_chunked(p,bad_crc=True)
            with self.assertRaisesRegex(ValueError,'CRC mismatch'):
                list(iter_mcap(p,[]))

    def test_uncompressed_chunk_validates_crc(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'plain.mcap'
            _,n=make_chunked(p,compression='none')
            self.assertEqual(len(list(iter_mcap(p,[]))),n)

    def test_truncated_file_missing_final_magic_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=make_mcap(Path(d)/'incomplete.mcap')
            p.write_bytes(p.read_bytes()[:-8])
            with self.assertRaisesRegex(ValueError,'footer/trailing magic'):
                list(iter_mcap(p,[]))

    def test_non_mcap_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fake.mcap';p.write_text('not an MCAP')
            with self.assertRaisesRegex(ValueError,'Not a valid MCAP'):
                list(iter_mcap(p,[]))


if __name__=='__main__': unittest.main()
