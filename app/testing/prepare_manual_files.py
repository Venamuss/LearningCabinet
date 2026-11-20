import argparse
from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

from testing.files import office_bytes, pdf_bytes, preview_mp4, wav_bytes


def write_boundary_wav(path, size):
    import struct

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

    with path.open("wb") as output:
        output.write(header)
        output.truncate(size)


def main():
    parser = argparse.ArgumentParser(
        description="Подготовка только синтетических файлов для ручной проверки."
    )
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    destination = arguments.output.resolve()

    if destination.is_relative_to(APP_DIR / "var"):
        parser.error("Нельзя создавать набор в рабочей папке app/var.")

    if destination.exists() and (
        not destination.is_dir() or any(destination.iterdir())
    ):
        parser.error(
            "Выберите новую или пустую папку. Существующие файлы не перезаписываются."
        )

    destination.mkdir(parents=True, exist_ok=True)
    files = {
        "lesson.txt": "Учебный материал для ручной проверки.\n".encode("utf-8"),
        "lesson.pdf": pdf_bytes(),
        "lesson.docx": office_bytes("docx"),
        "lesson.pptx": office_bytes("pptx"),
        "lesson.wav": wav_bytes(),
        "lesson.mp4": preview_mp4(),
        "unsupported.zip": office_bytes("docx"),
        "renamed_program.pdf": b"MZ\x00\x01\x02not-a-pdf",
        "empty.txt": b"",
    }
    fixtures = APP_DIR / "materials" / "tests" / "fixtures"

    for name in ("tone.mp3", "tone.ogg", "video.webm"):
        files[name] = (fixtures / name).read_bytes()

    for name, content in files.items():
        (destination / name).write_bytes(content)

    write_boundary_wav(destination / "exact_50_mib.wav", 52_428_800)
    write_boundary_wav(destination / "over_50_mib.wav", 52_428_801)
    print(f"Создан набор из {len(files) + 2} файлов: {destination}")
    print("Граничные WAV предназначены для проверки размера, а не для прослушивания.")


if __name__ == "__main__":
    main()
