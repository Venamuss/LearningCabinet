from pathlib import Path
import re
import struct
from urllib.parse import urlsplit
from zipfile import ZipFile

from defusedxml.ElementTree import fromstring
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from mutagen import File as AudioFile
from mutagen.mp3 import MP3
from mutagen.oggflac import OggFLAC
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE
from pypdf import PdfReader

MAX_UPLOAD_BYTES = 52_428_800
FORMATS = {
    ".pdf": ("application/pdf", "none"),
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "none",
    ),
    ".pptx": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "none",
    ),
    ".txt": ("text/plain", "none"),
    ".mp4": ("video/mp4", "video"),
    ".webm": ("video/webm", "video"),
    ".mp3": ("audio/mpeg", "audio"),
    ".ogg": ("audio/ogg", "audio"),
    ".wav": ("audio/wav", "audio"),
}


def validate_external_url(value):
    if any(ord(character) < 33 or ord(character) == 127 for character in value):
        raise ValidationError(
            "Ссылка не должна содержать пробелы или управляющие символы."
        )

    URLValidator(schemes=["http", "https"])(value)

    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme in ("http", "https")
            and parsed.hostname
            and parsed.username is None
            and parsed.password is None
        )
        parsed.port
    except ValueError as error:
        raise ValidationError("Укажите корректную HTTP(S)-ссылку.") from error

    if not valid:
        raise ValidationError("Укажите HTTP(S)-ссылку без логина и пароля в адресе.")


def validate_office(upload, extension):
    document_path = (
        "word/document.xml" if extension == ".docx" else "ppt/presentation.xml"
    )
    expected_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
        if extension == ".docx"
        else "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
    )
    expected_root = (
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document"
        if extension == ".docx"
        else "{http://schemas.openxmlformats.org/presentationml/2006/main}presentation"
    )

    with ZipFile(upload) as archive:
        entries = archive.infolist()

        if (
            len(entries) > 2000
            or sum(entry.file_size for entry in entries) > 200 * 1024 * 1024
        ):
            raise ValueError("Превышены ограничения проверки архива.")

        if any(
            entry.flag_bits & 1 or "vbaproject" in entry.filename.lower()
            for entry in entries
        ):
            raise ValueError("Зашифрованные документы и макросы не поддерживаются.")

        for name in ("[Content_Types].xml", "_rels/.rels", document_path):
            if archive.getinfo(name).file_size > 8 * 1024 * 1024:
                raise ValueError("Слишком большой XML-документ.")

        content_types = fromstring(archive.read("[Content_Types].xml"))
        fromstring(archive.read("_rels/.rels"))
        document = fromstring(archive.read(document_path))
        has_main_part = any(
            node.attrib.get("PartName") == f"/{document_path}"
            and node.attrib.get("ContentType") == expected_type
            for node in content_types
        )

        if not has_main_part or document.tag != expected_root:
            raise ValueError("Тип документа не соответствует расширению.")


def mp4_boxes(upload, start, end):
    position = start
    count = 0

    while position < end:
        count += 1

        if count > 10000 or end - position < 8:
            raise ValueError("Повреждён контейнер MP4.")

        upload.seek(position)
        size, name = struct.unpack(">I4s", upload.read(8))
        header_size = 8

        if size == 1:
            size = struct.unpack(">Q", upload.read(8))[0]
            header_size = 16
        elif size == 0:
            size = end - position

        if size < header_size or position + size > end:
            raise ValueError("Неверный размер блока MP4.")

        yield name, position + header_size, position + size
        position += size


def validate_mp4(upload):
    boxes = list(mp4_boxes(upload, 0, upload.size))
    names = {name for name, start, end in boxes}

    if not {b"ftyp", b"moov", b"mdat"}.issubset(names):
        raise ValueError("В MP4 отсутствуют обязательные блоки.")

    video_track = False
    media_data = False

    for name, start, end in boxes:
        if name == b"mdat" and end > start:
            media_data = True

        if name != b"moov":
            continue

        for child, child_start, child_end in mp4_boxes(upload, start, end):
            if child != b"trak":
                continue

            for track_child, track_start, track_end in mp4_boxes(
                upload, child_start, child_end
            ):
                if track_child != b"mdia":
                    continue

                for media_child, media_start, media_end in mp4_boxes(
                    upload, track_start, track_end
                ):
                    if media_child == b"hdlr" and media_end - media_start >= 12:
                        upload.seek(media_start + 8)
                        video_track = video_track or upload.read(4) == b"vide"

    if not video_track or not media_data:
        raise ValueError("В MP4 не найдены видеодорожка и данные.")


def ebml_number(upload, *, identifier=False):
    first = upload.read(1)

    if not first or first == b"\x00":
        raise ValueError("Повреждён заголовок WebM.")

    marker = 0x80
    length = 1

    while not first[0] & marker:
        marker >>= 1
        length += 1

    if length > (4 if identifier else 8):
        raise ValueError("Неверная длина поля WebM.")

    tail = upload.read(length - 1)

    if len(tail) != length - 1:
        raise ValueError("Оборванное поле WebM.")

    value = int.from_bytes(first + tail, "big")

    if identifier:
        return value

    value &= (1 << (7 * length)) - 1
    return None if value == (1 << (7 * length)) - 1 else value


def ebml_elements(upload, start, end):
    position = start
    count = 0

    while position < end:
        count += 1

        if count > 10000:
            raise ValueError("Слишком много элементов WebM.")

        upload.seek(position)
        identifier = ebml_number(upload, identifier=True)
        size = ebml_number(upload)
        payload_start = upload.tell()
        payload_end = end if size is None else payload_start + size

        if payload_end > end:
            raise ValueError("Неверный размер элемента WebM.")

        yield identifier, payload_start, payload_end
        position = payload_end


def validate_webm(upload):
    header_valid = False
    video_track = False
    media_data = False

    for identifier, start, end in ebml_elements(upload, 0, upload.size):
        if identifier == 0x1A45DFA3:
            for child, child_start, child_end in ebml_elements(upload, start, end):
                if child == 0x4282 and child_end - child_start == 4:
                    upload.seek(child_start)
                    header_valid = upload.read(4) == b"webm"

        if identifier != 0x18538067:
            continue

        for child, child_start, child_end in ebml_elements(upload, start, end):
            if child == 0x1F43B675 and child_end > child_start:
                media_data = True

            if child != 0x1654AE6B:
                continue

            for entry, entry_start, entry_end in ebml_elements(
                upload, child_start, child_end
            ):
                if entry != 0xAE:
                    continue

                track_type = None
                codec = b""

                for value_id, value_start, value_end in ebml_elements(
                    upload, entry_start, entry_end
                ):
                    if value_id == 0x83 and value_end - value_start <= 8:
                        upload.seek(value_start)
                        track_type = int.from_bytes(
                            upload.read(value_end - value_start), "big"
                        )
                    elif value_id == 0x86 and value_end - value_start <= 100:
                        upload.seek(value_start)
                        codec = upload.read(value_end - value_start)

                video_track = video_track or (
                    track_type == 1 and codec.startswith(b"V_")
                )

    if not header_valid or not video_track or not media_data:
        raise ValueError("Файл не является поддерживаемым WebM-видео.")


def validate_text(upload):
    data = upload.read(MAX_UPLOAD_BYTES + 1)

    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16")
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1251")

    if any(
        not character.isprintable() and character not in "\r\n\t\f"
        for character in text
    ):
        raise ValueError("Текст содержит бинарные данные.")

    if re.search(r"<!doctype\s+html|<html\b|<script\b|<svg\b", text, re.IGNORECASE):
        raise ValueError("HTML и SVG не поддерживаются.")


def validate_upload(upload):
    extension = Path(upload.name).suffix.lower()

    if extension not in FORMATS:
        raise ValidationError(
            "Формат файла не поддерживается. Выберите разрешённый тип."
        )

    if upload.size <= 0:
        raise ValidationError("Файл пуст.")

    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Размер файла не должен превышать 50 МБ.")

    try:
        upload.seek(0)

        if extension == ".pdf":
            if not upload.read(8).startswith(b"%PDF-"):
                raise ValueError("Неверная сигнатура PDF.")

            upload.seek(0)
            document = PdfReader(upload, strict=True)

            if document.is_encrypted or not document.pages:
                raise ValueError("Зашифрованный или пустой PDF.")

            for page in document.pages:
                page.mediabox
        elif extension in (".docx", ".pptx"):
            validate_office(upload, extension)
        elif extension == ".txt":
            validate_text(upload)
        elif extension == ".mp4":
            validate_mp4(upload)
        elif extension == ".webm":
            validate_webm(upload)
        else:
            if extension == ".mp3":
                audio = MP3(upload)
            elif extension == ".wav":
                audio = WAVE(upload)
            else:
                audio = AudioFile(upload)

                if not isinstance(audio, (OggVorbis, OggOpus, OggFLAC)):
                    raise ValueError("Ожидался поддерживаемый Ogg-аудиофайл.")

            if audio.info.length <= 0:
                raise ValueError("В аудиофайле отсутствуют данные.")
    except ValidationError:
        raise
    except Exception as error:
        raise ValidationError(
            "Файл повреждён, защищён или его содержимое не соответствует расширению."
        ) from error
    finally:
        upload.seek(0)

    return FORMATS[extension]
