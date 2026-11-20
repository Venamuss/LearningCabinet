from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from materials.validators import (
    FORMATS,
    MAX_UPLOAD_BYTES,
    validate_external_url,
    validate_upload,
)
from testing.files import boundary_wav, office_bytes, pdf_bytes, preview_mp4, wav_bytes


class UploadValidationUnitTests(SimpleTestCase):
    def test_exactly_nine_extensions_are_supported(self):
        self.assertEqual(
            set(FORMATS),
            {".pdf", ".docx", ".pptx", ".txt", ".mp4", ".webm", ".mp3", ".ogg", ".wav"},
        )

    def test_valid_documents_and_media_detected_by_content(self):
        fixtures = Path(__file__).parent / "fixtures"
        cases = [
            ("example.pdf", pdf_bytes(), "application/pdf", "none"),
            ("example.docx", office_bytes("docx"), FORMATS[".docx"][0], "none"),
            ("example.pptx", office_bytes("pptx"), FORMATS[".pptx"][0], "none"),
            ("example.TXT", "Задание".encode(), "text/plain", "none"),
            ("example.wav", wav_bytes(), "audio/wav", "audio"),
            ("example.mp4", preview_mp4(), "video/mp4", "video"),
            (
                "example.mp3",
                (fixtures / "tone.mp3").read_bytes(),
                "audio/mpeg",
                "audio",
            ),
            ("example.ogg", (fixtures / "tone.ogg").read_bytes(), "audio/ogg", "audio"),
            (
                "example.webm",
                (fixtures / "video.webm").read_bytes(),
                "video/webm",
                "video",
            ),
        ]

        for name, content, mime_type, media_kind in cases:
            with self.subTest(name=name):
                upload = SimpleUploadedFile(
                    name, content, content_type="application/x-false"
                )
                self.assertEqual(validate_upload(upload), (mime_type, media_kind))
                self.assertEqual(upload.tell(), 0)

    def test_corrupt_renamed_and_unsupported_files_rejected(self):
        cases = [
            ("empty.txt", b""),
            ("binary.txt", b"MZ\x00\x01\x02"),
            ("page.txt", b"<!doctype html><html><script>alert(1)</script></html>"),
            ("program.pdf", b"MZ\x00executable"),
            ("broken.pdf", b"%PDF-1.7\nbroken"),
            ("archive.docx", b"PK\x03\x04broken"),
            ("presentation.docx", office_bytes("pptx")),
            ("document.pptx", office_bytes("docx")),
            ("macro.docx", office_bytes("docx", macro=True)),
            ("fake.mp4", b"not a video"),
            ("fake.webm", b"\x1a\x45\xdf\xa3\x80"),
            ("fake.mp3", b"ID3not-an-audio-stream"),
            ("fake.ogg", b"OggSnot-an-audio-stream"),
            ("fake.wav", b"RIFFnot-a-wave"),
            ("archive.zip", office_bytes("docx")),
            ("image.svg", b"<svg/>"),
        ]

        for name, content in cases:
            with self.subTest(name=name):
                with self.assertRaises(ValidationError):
                    validate_upload(SimpleUploadedFile(name, content))

    def test_supported_text_encodings(self):
        for encoding in ("utf-8", "utf-8-sig", "utf-16", "cp1251"):
            with self.subTest(encoding=encoding):
                upload = SimpleUploadedFile(
                    "Задание.txt", "Текст\r\nЗадание".encode(encoding)
                )
                self.assertEqual(validate_upload(upload), ("text/plain", "none"))

    def test_exact_fifty_mebibyte_valid_wav_is_accepted(self):
        upload = boundary_wav(MAX_UPLOAD_BYTES)

        try:
            self.assertEqual(
                Path(upload.temporary_file_path()).stat().st_size, MAX_UPLOAD_BYTES
            )
            self.assertEqual(validate_upload(upload), ("audio/wav", "audio"))
        finally:
            upload.close()

    def test_one_byte_over_limit_is_rejected(self):
        upload = boundary_wav(MAX_UPLOAD_BYTES + 1)

        try:
            self.assertEqual(
                Path(upload.temporary_file_path()).stat().st_size, MAX_UPLOAD_BYTES + 1
            )

            with self.assertRaises(ValidationError):
                validate_upload(upload)
        finally:
            upload.close()


class ExternalUrlUnitTests(SimpleTestCase):
    def test_http_https_and_unicode_host_are_accepted_without_network(self):
        with patch(
            "socket.socket.connect", side_effect=AssertionError("Network is forbidden")
        ):
            for value in (
                "https://example.org/video.mp4",
                "http://127.0.0.1:8766/demo.wav",
                "https://пример.рф/урок",
            ):
                with self.subTest(value=value):
                    validate_external_url(value)

    def test_unsafe_urls_are_rejected(self):
        for value in (
            "javascript:alert(1)",
            "data:video/mp4,AAAA",
            "file:///etc/passwd",
            "/relative/path",
            "//example.org/file",
            "https://user:password@example.org/file",
            "https://example.org/file\n",
            "https://example.org/a b",
            "https://example.org:99999/file",
            "https://",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_external_url(value)
