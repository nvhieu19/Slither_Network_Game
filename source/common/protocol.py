"""UTF-8 JSON followed by LF; TCP chunk boundaries are never packet boundaries."""
import json
import math


class ProtocolError(ValueError):
    pass


def encode_packet(packet):
    if not isinstance(packet, dict):
        raise ProtocolError("Packet must be an object")
    try:
        return (json.dumps(packet, ensure_ascii=False, separators=(",", ":"),
                           allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProtocolError("Invalid JSON value") from exc


def _reject_constant(value):
    raise ProtocolError("Non-finite JSON number")


class FrameDecoder:
    def __init__(self, max_frame=262144):
        self.buffer = bytearray()
        self.max_frame = max_frame

    def feed(self, chunk):
        self.buffer.extend(chunk)
        result = []
        while b"\n" in self.buffer:
            end = self.buffer.index(10)
            if end > self.max_frame:
                raise ProtocolError("Frame too large")
            raw = bytes(self.buffer[:end])
            del self.buffer[:end + 1]
            try:
                item = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
            except (ValueError, UnicodeError, RecursionError) as exc:
                raise ProtocolError("Malformed JSON frame") from exc
            if not isinstance(item, dict) or not isinstance(item.get("type"), str):
                raise ProtocolError("Missing message type")
            result.append(item)
        if len(self.buffer) > self.max_frame:
            raise ProtocolError("Frame too large")
        return result


def finite_number(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ProtocolError("Expected number")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ProtocolError("Number out of range")
    return float(value)
