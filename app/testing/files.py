from io import BytesIO
from pathlib import Path
import struct
import wave
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from pypdf import PdfWriter


def text_upload(content="Учебный материал", name="Материал.txt"):
    return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/plain")


def pdf_bytes():
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(output)
    return output.getvalue()


def office_bytes(extension="docx", *, macro=False):
    word = extension == "docx"
    part = "word/document.xml" if word else "ppt/presentation.xml"
    content_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
        if word
        else "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
    )
    document = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Материал</w:t></w:r></w:p><w:sectPr/></w:body></w:document>"
        if word
        else '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:sldIdLst/><p:sldSz cx="9144000" cy="6858000"/>'
        '<p:notesSz cx="6858000" cy="9144000"/></p:presentation>'
    )
    output = BytesIO()

    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            f'<Override PartName="/{part}" ContentType="{content_type}"/></Types>',
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            f'Target="{part}"/></Relationships>',
        )
        archive.writestr(part, document)

        if macro:
            archive.writestr("word/vbaProject.bin", b"macro")

    return output.getvalue()


def wav_bytes():
    output = BytesIO()

    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(1)
        audio.setframerate(8000)
        audio.writeframes(b"\x80" * 800)

    return output.getvalue()


def boundary_wav(size):
    upload = TemporaryUploadedFile("boundary.wav", "audio/wav", size, None)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        size - 8,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        8000,
        8000,
        1,
        8,
        b"data",
        size - 44,
    )
    upload.write(header)
    upload.file.truncate(size)
    upload.seek(0)
    return upload


def preview_mp4():
    return (
        Path(__file__).resolve().parent.parent / "preview_assets" / "demo.mp4"
    ).read_bytes()
