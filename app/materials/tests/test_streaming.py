from io import BytesIO

from django.test import SimpleTestCase

from materials.streaming import FileSegment, InvalidRange, parse_range


class RangeUnitTests(SimpleTestCase):
    def test_valid_closed_open_suffix_and_clipped_ranges(self):
        for value, expected in (
            ("bytes=0-0", (0, 0)),
            ("bytes=2-5", (2, 5)),
            ("bytes=7-", (7, 9)),
            ("bytes=-3", (7, 9)),
            ("bytes=-30", (0, 9)),
            ("bytes=8-999", (8, 9)),
        ):
            with self.subTest(header=value):
                self.assertEqual(parse_range(value, 10), expected)

    def test_no_unknown_or_multiple_ranges_mean_full_response(self):
        for value in ("", "items=1-2", "bytes=0-0,2-2"):
            with self.subTest(header=value):
                self.assertIsNone(parse_range(value, 10))

    def test_malformed_and_unsatisfiable_ranges_rejected(self):
        for value in (
            "bytes",
            "bytes=",
            "bytes=-",
            "bytes=-0",
            "bytes=10-",
            "bytes=8-2",
            "bytes=a-2",
            "bytes=0-" + "9" * 201,
        ):
            with self.subTest(header=value):
                with self.assertRaises(InvalidRange):
                    parse_range(value, 10)

    def test_zero_length_range_rejected(self):
        with self.assertRaises(InvalidRange):
            parse_range("bytes=0-0", 0)


class FileSegmentUnitTests(SimpleTestCase):
    def test_only_requested_bytes_read_and_handle_closed(self):
        handle = BytesIO(b"0123456789")
        self.assertEqual(b"".join(FileSegment(handle, 2, 4)), b"2345")
        self.assertTrue(handle.closed)

    def test_chunks_are_bounded(self):
        handle = BytesIO(b"x" * 150000)
        chunks = list(FileSegment(handle, 0, 150000))
        self.assertEqual(sum(map(len, chunks)), 150000)
        self.assertLessEqual(max(map(len, chunks)), 64 * 1024)
        self.assertTrue(handle.closed)

    def test_close_before_iteration_and_after_disconnect(self):
        for started in (False, True):
            with self.subTest(started=started):
                handle = BytesIO(b"x" * 100000)
                segment = FileSegment(handle, 0, 100000)

                if started:
                    next(segment)

                segment.close()
                self.assertTrue(handle.closed)

    def test_truncated_resource_and_empty_segment_close(self):
        for data, length in ((b"short", 20), (b"data", 0)):
            with self.subTest(length=length):
                handle = BytesIO(data)
                list(FileSegment(handle, 0, length))
                self.assertTrue(handle.closed)

    def test_read_exception_closes_handle(self):
        class BrokenFile(BytesIO):
            def read(self, size=-1):
                raise OSError("Simulated read error")

        handle = BrokenFile(b"data")

        with self.assertRaises(OSError):
            next(FileSegment(handle, 0, 4))

        self.assertTrue(handle.closed)
