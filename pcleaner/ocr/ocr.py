from pathlib import Path
from typing import Protocol, TypeAlias, Callable
from io import StringIO
import itertools
import csv

from PIL import Image
from natsort import natsorted
from loguru import logger

import pcleaner.config as cfg
import pcleaner.structures as st
import pcleaner.helpers as hp
from pcleaner.ocr.ocr_mangaocr import MangaOcr
from pcleaner.ocr.ocr_tesseract import TesseractOcr
import pcleaner.ocr.supported_languages as osl
from pcleaner.ocr.parsers import TRANSLATION_MARKER


class OCRModel(Protocol):
    def __call__(self, img_or_path: Image.Image | Path | str, **kwargs) -> str: ...


OCREngineFactory: TypeAlias = Callable[[osl.LanguageCode], OCRModel]


def tesseract_ok(profile: cfg.Profile) -> bool:
    want_tess = profile.preprocessor.ocr_use_tesseract
    has_language_packs: bool = bool(TesseractOcr.langs())
    return not want_tess or (want_tess and has_language_packs)


def ocr_engines():
    return {
        cfg.OCREngine.MANGAOCR: MangaOcr(),
        cfg.OCREngine.TESSERACT: TesseractOcr(),
    }


def get_all_available_langs() -> set[osl.LanguageCode]:
    union_langs = set()
    for ocr in ocr_engines().values():
        union_langs |= ocr.langs()
    return union_langs


def build_ocr_engine_factory(
    tesseract_enabled: bool, ocr_engine_preference: cfg.OCREngine
) -> OCREngineFactory:
    """
    Create a factory function that returns the appropriate OCR engine for a given language.

    :param tesseract_enabled: Whether Tesseract should be considered for use.
    :param ocr_engine_preference: The preferred OCR engine.
    :return: The factory function.
    """
    # want_tess = profile.preprocessor.ocr_use_tesseract
    tess_langs: set[osl.LanguageCode] = TesseractOcr.langs()
    mocr_langs: set[osl.LanguageCode] = MangaOcr.langs()
    if tesseract_enabled and not tess_langs:
        logger.error(
            f"Tesseract OCR is not installed or not found. "
            "Please see the instructions in the README to install Tesseract correctly. Falling back to manga-ocr."
        )

    if not tesseract_enabled:
        ocr_engine_preference = cfg.OCREngine.MANGAOCR

    def closure(lang: osl.LanguageCode) -> OCRModel:
        if ocr_engine_preference == cfg.OCREngine.AUTO:
            # Prefer MangaOCR for the languages it can do, which is only one, but it's
            # much better than Tesseract for it.
            if lang in mocr_langs:
                # The linter is being retarded here.
                # noinspection PyTypeChecker
                return MangaOcr()
            if lang in tess_langs:
                return TesseractOcr(lang)
        elif ocr_engine_preference == cfg.OCREngine.TESSERACT:
            if lang in tess_langs:
                return TesseractOcr(lang)
            logger.error(
                f"Tesseract language pack for '{lang}' is not installed or not found. "
                "Please see the instructions to install Tesseract correctly. Falling back to manga-ocr."
            )
        # Fall back to manga-ocr.
        # noinspection PyTypeChecker
        return MangaOcr()

    return closure


def format_output(
    ocr_analytics: list[st.OCRAnalytic],
    csv_output: bool,
    csv_column_names: tuple[str, ...],
    translations: dict[Path, list[str]] | None = None,
) -> str:
    """
    Format the output of the OCR process.

    :param ocr_analytics: A list of the OCR analytics per image.
    :param csv_output: If True, output the data in CSV format, otherwise in plain text.
    :param csv_column_names: The (localized) names of the columns in the CSV output:
        filename, startx, starty, endx, endy, text, and translation if translations are given.
    :param translations: [Optional] Translations per analytic path, one per entry in removed_box_data.
        When given, a translation column (CSV) or translation lines (plain text) are added.
    :return: The formatted output.
    """
    # Format of the analytics:
    # number of boxes | sizes of all boxes | sizes of boxes that were OCRed | path to image, text, box coordinates
    # We do not need to show the first three columns, so we simplify the data structure.
    # path_texts_coords: list[tuple[Path, str, st.Box]] = list(
    #     itertools.chain.from_iterable(a.removed_box_data for a in ocr_analytics)
    # )

    # Build tuples of the form (path, text, box, translation) for the removed texts.
    # This requires adding the path from the analytic to all the texts.
    path_texts_coords: list[tuple[Path, str, st.Box, str | None]] = []
    for analytic in ocr_analytics:
        page_translations = None if translations is None else translations.get(analytic.path, [])
        for index, (text, box) in enumerate(analytic.removed_box_data):
            translation = None
            if page_translations is not None:
                translation = page_translations[index] if index < len(page_translations) else ""
            path_texts_coords.append((analytic.path, text, box, translation))

    if path_texts_coords:
        paths, texts, boxes, translated = zip(*path_texts_coords)
        paths = hp.trim_prefix_from_paths(paths)
        path_texts_coords = list(zip(paths, texts, boxes, translated))
        # Sort by path. The sort is stable, so the bubble order within a page is kept.
        path_texts_coords = natsorted(path_texts_coords, key=lambda x: x[0])

    if csv_output:
        return format_output_csv(path_texts_coords, csv_column_names, translations is not None)
    return format_output_plain(path_texts_coords)


def format_output_csv(
    path_texts_coords: list[tuple[Path, str, st.Box, str | None]],
    csv_column_names: tuple[str, ...],
    with_translation: bool = False,
) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)
    if with_translation and len(csv_column_names) == 6:
        csv_column_names = (*csv_column_names, "translation")
    writer.writerow(csv_column_names[: 7 if with_translation else 6])

    for path, bubble, box, translation in path_texts_coords:
        if "\n" in bubble:
            logger.warning(f"Detected newline in bubble: {path} {bubble} {box}")
            bubble = bubble.replace("\n", "\\n")
        row = [path, *box.as_tuple, bubble]
        if with_translation:
            row.append((translation or "").replace("\n", "\\n"))
        writer.writerow(row)

    return buffer.getvalue()


def format_output_plain(path_texts_coords: list[tuple[Path, str, st.Box, str | None]]) -> str:
    # Place the file path on it's own line, and only if it's different from the previous one.
    # Translations are placed on the line after their bubble, prefixed with the marker.
    buffer = StringIO()
    current_path = ""
    for path, bubble, _, translation in path_texts_coords:
        if path != current_path:
            buffer.write(f"\n\n{path}: ")
            current_path = path
        buffer.write(f"\n{bubble}")
        if "\n" in bubble:
            logger.warning(f"Detected newline in bubble: {path} {bubble}")
        if translation is not None:
            translation = translation.replace("\n", " ")
            buffer.write(f"\n{TRANSLATION_MARKER}{translation}")

    return buffer.getvalue()
