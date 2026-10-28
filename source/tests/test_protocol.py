import unittest
from common.protocol import FrameDecoder, ProtocolError, encode_packet, finite_number


class ProtocolTests(unittest.TestCase):
    def test_fragmented_unicode_and_coalesced_frames(self):
        packets=[{"type":"CHAT","text":"Xin chào 🐍\nDòng hai"},{"type":"PING","stamp":1}]
        data=b"".join(encode_packet(p) for p in packets)
        reader=FrameDecoder(); result=[]
        for byte in data: result+=reader.feed(bytes([byte]))
        self.assertEqual(result,packets)
        self.assertEqual(FrameDecoder().feed(data),packets)

    def test_reject_invalid_json_shape_and_nonfinite(self):
        for data in [b'[]\n',b'{"type":"X","n":NaN}\n',b'{broken}\n',b'{}\n',b'\xff\n']:
            with self.subTest(data=data),self.assertRaises(ProtocolError):
                FrameDecoder().feed(data)

    def test_frame_limit(self):
        with self.assertRaises(ProtocolError): FrameDecoder(20).feed(b'a'*21)
        with self.assertRaises(ProtocolError): FrameDecoder(20).feed(b'a'*21+b'\n')

    def test_numbers(self):
        for n in [True,"1",float("inf"),float("nan"),-11]:
            with self.assertRaises(ProtocolError): finite_number(n,-10,10)
        self.assertEqual(finite_number(2,-10,10),2)

    def test_encoder_disallows_nan(self):
        with self.assertRaises(ProtocolError): encode_packet({"type":"X","value":float("nan")})
