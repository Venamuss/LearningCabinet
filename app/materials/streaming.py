import re


class InvalidRange(ValueError):
    pass


def parse_range(value, size):
    if not value:
        return None

    unit, separator, expression = value.partition("=")

    if unit.strip().lower() != "bytes":
        return None

    if not separator or len(value) > 200:
        raise InvalidRange

    if "," in expression:
        return None

    match = re.fullmatch(r"([0-9]*)-([0-9]*)", expression.strip())

    if not match or size == 0:
        raise InvalidRange

    start_text, end_text = match.groups()

    if not start_text:
        if not end_text or int(end_text) <= 0:
            raise InvalidRange

        return max(0, size - int(end_text)), size - 1

    start = int(start_text)
    end = min(int(end_text), size - 1) if end_text else size - 1

    if start >= size or end < start:
        raise InvalidRange

    return start, end


class FileSegment:
    def __init__(self, handle, start, length):
        self.handle = handle
        self.remaining = length
        self.handle.seek(start)

    def __iter__(self):
        return self

    def __next__(self):
        if self.remaining <= 0 or self.handle.closed:
            self.close()
            raise StopIteration

        try:
            chunk = self.handle.read(min(self.remaining, 64 * 1024))
        except Exception:
            self.close()
            raise

        if not chunk:
            self.close()
            raise StopIteration

        self.remaining -= len(chunk)
        return chunk

    def close(self):
        self.handle.close()
