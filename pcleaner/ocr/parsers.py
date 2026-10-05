from pathlib import Path
from csv import reader
from enum import Enum, auto
from attrs import frozen
from collections import defaultdict

import pcleaner.structures as st

# Prefix for translation lines in the plain text output. These lines are skipped when parsing.
TRANSLATION_MARKER = "→ "


class ParseErrorCode(Enum):
    OS_ERROR = auto()
    OTHER_ERROR = auto()
    NOT_6_COLUMNS = auto()
    NOT_AN_INT = auto()
    INT_TOO_BIG = auto()
    INVALID_FORMAT = auto()
    INVALID_CSV_HEADER = auto()
    NO_FILE_PATH = auto()
    INVALID_PATH = auto()


@frozen
class ParseError:
    """
    Store enough information to inform the user about parse errors.
    Use error codes to allow for easy i18n.
    """

    line: int
    error_code: ParseErrorCode
    context: str


def parse_plain_text(path: Path) -> tuple[list[st.OCRAnalytic], list[ParseError]]:
    analytics, _, errors = _parse_plain_text(path)
    return analytics, errors


def _parse_plain_text(
    path: Path,
) -> tuple[list[st.OCRAnalytic], dict[Path, list[str]], list[ParseError]]:
    """
    Try to load the file, assuming it's a plain text file.
    If it isn't, raise a FileNotPlain Error, along with relevant
    parse errors.

    Valid example:

    myfile.jpg:
    This is some text.
    This is some more text.

    anotherfile.jpg:
    This is some text.

    Translation lines, starting with the translation marker, belong to the bubble above them.

    :param path: The path to the supposed csv file.
    :return: A list of analytics, the translations per path and a list of errors.
        Either the analytics or the errors will be empty.
    """

    analytics_data: dict[Path, list[tuple[str, st.Box]]] = defaultdict(list)
    translation_data: dict[Path, list[str]] = defaultdict(list)
    parse_errors: list[ParseError] = []

    with path.open("r", encoding="utf-8") as file:
        lines = file.readlines()

    current_path = None
    expecting_file_path = True

    for line_number, line in enumerate(lines, start=1):
        stripped_line = line.strip()

        # Simple 2-state machine to parse the plain text file.
        if expecting_file_path:
            # Ignore consecutive empty lines.
            if not stripped_line:
                continue

            if len(stripped_line) > 1 and stripped_line.endswith(":"):
                current_path = Path(stripped_line[:-1])
                expecting_file_path = False
                continue
            else:
                parse_errors.append(
                    ParseError(
                        line=line_number, error_code=ParseErrorCode.INVALID_PATH, context=line
                    )
                )
                continue

        else:
            if not stripped_line:
                expecting_file_path = True
                continue
            elif stripped_line.startswith(TRANSLATION_MARKER.strip()):
                # Translations aren't part of the OCR data, attach them to the bubble above.
                if analytics_data[current_path]:
                    translation = stripped_line[len(TRANSLATION_MARKER.strip()) :].strip()
                    translation_data[current_path][-1] = translation
                continue
            else:
                text = stripped_line
                box = st.Box(-1, -1, -1, -1)
                analytics_data[current_path].append((text, box))
                translation_data[current_path].append("")

    if parse_errors:
        return [], {}, parse_errors

    # Pack the analytics data by file path.
    analytics_list = []
    for file_path, box_data in analytics_data.items():
        if not box_data:
            continue
        analytics_list.append(st.OCRAnalytic(file_path, len(box_data), [], [], box_data))

    return analytics_list, dict(translation_data), []


def parse_csv(path: Path) -> tuple[list[st.OCRAnalytic], list[ParseError]]:
    analytics, _, errors = _parse_csv(path)
    return analytics, errors


def _parse_csv(path: Path) -> tuple[list[st.OCRAnalytic], dict[Path, list[str]], list[ParseError]]:
    """
    Try to load the file, assuming it's a csv file.
    If it isn't, raise a FileNotCSV Error, along with relevant
    parse errors.

    Valid example:

    filename,startx,starty,endx,endy,text
    img1.jpg,923,73,1011,336,sample text
    img1.jpg,423,73,711,336,"something else, perhaps"
    img2.jpg,534,275,592,414,or nothing at all

    A 7th translation column is allowed.

    :param path: The path to the supposed csv file.
    :return: A list of analytics, the translations per path and a list of errors.
        Either the analytics or the errors will be empty.
    """
    analytics_data: dict[Path, list[tuple[str, st.Box]]] = defaultdict(list)
    translation_data: dict[Path, list[str]] = defaultdict(list)
    parse_errors: list[ParseError] = []

    with path.open("r", encoding="utf-8") as file:
        csv_reader = reader(file)
        header = next(csv_reader)

        # The header must not contain any digits.
        # If it does, then someone likely removed the header and now has box coordinates
        # in here, which would get ignored.
        if len(header) not in (6, 7) or any(h.isdigit() for h in header):
            parse_errors.append(
                ParseError(
                    line=1,
                    error_code=ParseErrorCode.INVALID_CSV_HEADER,
                    context=",".join(header),
                )
            )
            return [], {}, parse_errors

        for line_number, row in enumerate(csv_reader, start=2):
            # Each row needs as many columns as the header (6, or 7 with translations).
            if len(row) != len(header):
                parse_errors.append(
                    ParseError(
                        line=line_number,
                        error_code=ParseErrorCode.NOT_6_COLUMNS,
                        context=",".join(row),
                    )
                )
                continue

            filename, startx, starty, endx, endy, text = row[:6]

            try:
                startx = int(startx)
                starty = int(starty)
                endx = int(endx)
                endy = int(endy)
            except ValueError:
                parse_errors.append(
                    ParseError(
                        line=line_number,
                        error_code=ParseErrorCode.NOT_AN_INT,
                        context=",".join(row),
                    )
                )
                continue
            # Make sure none of the ints is too big for a signed 32-bit int,
            # otherwise Qt can't render the boxes.
            if any(abs(i) > 2**31 - 1 for i in (startx, starty, endx, endy)):
                parse_errors.append(
                    ParseError(
                        line=line_number,
                        error_code=ParseErrorCode.INT_TOO_BIG,
                        context=",".join(row),
                    )
                )
                continue

            # Ensure the x and y values are coordinates, such that
            # startx <= endx (analogous for y). Otherwise they don't
            # form a valid box.
            startx, endx = min(startx, endx), max(startx, endx)
            starty, endy = min(starty, endy), max(starty, endy)

            if not filename:
                parse_errors.append(
                    ParseError(
                        line=line_number,
                        error_code=ParseErrorCode.NO_FILE_PATH,
                        context=",".join(row),
                    )
                )
                continue

            try:
                file_path = Path(filename)
            except Exception:
                parse_errors.append(
                    ParseError(
                        line=line_number,
                        error_code=ParseErrorCode.INVALID_PATH,
                        context=",".join(row),
                    )
                )
                continue

            box = st.Box(startx, starty, endx, endy)

            analytics_data[file_path].append((text, box))
            translation = row[6].replace("\\n", "\n") if len(row) > 6 else ""
            translation_data[file_path].append(translation)

    if parse_errors:
        return [], {}, parse_errors

    # Pack the analytics data by file path.
    analytics_list = []
    for file_path, box_data in analytics_data.items():
        analytics_list.append(st.OCRAnalytic(file_path, len(box_data), [], [], box_data))

    return analytics_list, dict(translation_data), []


def parse_ocr_data(path: Path) -> tuple[list[st.OCRAnalytic], list[ParseError]]:
    """
    Parse the OCR data from the file at the given path.
    The file can be either a plain text file or a CSV file.

    :param path: The path to the OCR data file.
    :return: A list of analytics and a list of errors.
    """
    try:
        if path.suffix == ".csv":
            return parse_csv(path)
        elif path.suffix == ".txt":
            return parse_plain_text(path)
        else:
            return [], [ParseError(line=-1, error_code=ParseErrorCode.INVALID_FORMAT, context="")]
    except OSError as e:
        return [], [ParseError(line=-1, error_code=ParseErrorCode.OS_ERROR, context=str(e))]
    except Exception as e:
        return [], [ParseError(line=-1, error_code=ParseErrorCode.OTHER_ERROR, context=str(e))]


def parse_translation_data(
    path: Path,
) -> tuple[list[st.OCRAnalytic], dict[Path, list[str]], list[ParseError]]:
    """
    Parse a translated OCR output file, keeping the translations.
    Bubbles without a translation get an empty string.

    :param path: The path to the translated OCR data file (.csv or .txt).
    :return: A list of analytics, the translations per analytic path (one per bubble),
        and a list of errors.
    """
    try:
        if path.suffix == ".csv":
            return _parse_csv(path)
        elif path.suffix == ".txt":
            return _parse_plain_text(path)
        else:
            return (
                [],
                {},
                [ParseError(line=-1, error_code=ParseErrorCode.INVALID_FORMAT, context="")],
            )
    except OSError as e:
        return [], {}, [ParseError(line=-1, error_code=ParseErrorCode.OS_ERROR, context=str(e))]
    except Exception as e:
        return [], {}, [ParseError(line=-1, error_code=ParseErrorCode.OTHER_ERROR, context=str(e))]
