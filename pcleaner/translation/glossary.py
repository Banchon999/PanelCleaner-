import csv
import json
from pathlib import Path

from attrs import frozen
from loguru import logger


@frozen
class GlossaryEntry:
    """
    A single glossary term.

    source: The term as it appears in the original text.
    target: The required translation of the term.
    note: [Optional] Extra context for the translator, e.g. "main character, female".
    """

    source: str
    target: str
    note: str = ""


class GlossaryError(Exception):
    pass


class Glossary:
    """
    A list of terms that must be translated consistently, such as character names,
    places or attack names.

    Supported file formats:

    CSV (header row optional, the note column is optional):

        source,target,note
        ルフィ,ลูฟี่,main character
        ゴムゴムの,หนังยาง,attack prefix

    JSON, either a plain mapping or a list of objects:

        {"ルフィ": "ลูฟี่", "ゾロ": "โซโล"}
        [{"source": "ルフィ", "target": "ลูฟี่", "note": "main character"}]
    """

    def __init__(self, entries: list[GlossaryEntry] | None = None) -> None:
        entries = entries or []
        # Deduplicate by source term, later entries win.
        unique: dict[str, GlossaryEntry] = {}
        for entry in entries:
            if entry.source and entry.target:
                unique[entry.source] = entry
        # Sort longest first, so longer terms take precedence when they contain shorter ones.
        self.entries: list[GlossaryEntry] = sorted(
            unique.values(), key=lambda e: len(e.source), reverse=True
        )

    def __len__(self) -> int:
        return len(self.entries)

    def __bool__(self) -> bool:
        return bool(self.entries)

    @classmethod
    def load(cls, path: Path | str) -> "Glossary":
        """
        Load a glossary from a CSV or JSON file.

        :param path: The path to the glossary file.
        :return: The loaded glossary.
        :raises GlossaryError: If the file can't be read or has an invalid format.
        """
        path = Path(path).expanduser()
        if not path.is_file():
            raise GlossaryError(f"Glossary file not found: {path}")

        try:
            # utf-8-sig strips the BOM that spreadsheet programs like to add.
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as e:
            raise GlossaryError(f"Failed to read glossary file {path}: {e}") from e

        if path.suffix.lower() == ".json":
            entries = cls._parse_json(content, path)
        else:
            entries = cls._parse_csv(content)

        glossary = cls(entries)
        logger.info(f"Loaded {len(glossary)} glossary entries from {path}")
        return glossary

    @staticmethod
    def _parse_csv(content: str) -> list[GlossaryEntry]:
        entries = []
        rows = list(csv.reader(content.splitlines()))
        if rows and [c.strip().lower() for c in rows[0][:2]] == ["source", "target"]:
            rows = rows[1:]
        for row in rows:
            row = [c.strip() for c in row]
            # Skip blank lines and comments.
            if not row or not any(row) or row[0].startswith("#"):
                continue
            if len(row) < 2:
                logger.warning(f"Skipping glossary row without a translation: {row}")
                continue
            note = ",".join(row[2:]).strip() if len(row) > 2 else ""
            entries.append(GlossaryEntry(row[0], row[1], note))
        return entries

    @staticmethod
    def _parse_json(content: str, path: Path) -> list[GlossaryEntry]:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise GlossaryError(f"Invalid JSON in glossary file {path}: {e}") from e

        if isinstance(data, dict):
            return [GlossaryEntry(str(k).strip(), str(v).strip()) for k, v in data.items()]
        if isinstance(data, list):
            entries = []
            for item in data:
                if not isinstance(item, dict) or "source" not in item or "target" not in item:
                    raise GlossaryError(
                        f"Glossary list entries need 'source' and 'target' keys, got: {item}"
                    )
                entries.append(
                    GlossaryEntry(
                        str(item["source"]).strip(),
                        str(item["target"]).strip(),
                        str(item.get("note", "")).strip(),
                    )
                )
            return entries
        raise GlossaryError(f"Glossary file {path} must contain a JSON object or list.")

    def find_matches(self, texts: list[str]) -> list[GlossaryEntry]:
        """
        Find all glossary entries whose source term appears in any of the given texts.
        Matching is case-insensitive.

        :param texts: The texts to search.
        :return: The matching entries, longest source term first.
        """
        haystack = "\n".join(texts).casefold()
        return [entry for entry in self.entries if entry.source.casefold() in haystack]


def add_glossary_entry(path: Path | str, entry: GlossaryEntry) -> None:
    """
    Add a term to a glossary file, replacing an existing entry with the same source term.
    The file is created if it doesn't exist yet, as CSV unless it has a .json suffix.

    :param path: The path to the glossary file.
    :param entry: The term to add.
    :raises GlossaryError: If the existing file can't be read or written.
    """
    path = Path(path).expanduser()
    if not entry.source.strip() or not entry.target.strip():
        raise GlossaryError("Both the source term and its translation are required.")
    is_json = path.suffix.lower() == ".json"
    entries: list[GlossaryEntry] = []
    if path.is_file():
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as e:
            raise GlossaryError(f"Failed to read glossary file {path}: {e}") from e
        entries = Glossary._parse_json(content, path) if is_json else Glossary._parse_csv(content)

    # Keep the user's order: replace the term in place, or append it at the end.
    sources = [e.source for e in entries]
    is_new_term = entry.source not in sources
    if is_new_term:
        entries.append(entry)
    else:
        entries[sources.index(entry.source)] = entry

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not is_json and is_new_term and path.is_file():
            # Append a single row, so comments and formatting in the file are kept.
            with path.open("r+", encoding="utf-8", newline="") as file:
                content = file.read()
                if content and not content.endswith(("\n", "\r")):
                    file.write("\n")
                csv.writer(file, lineterminator="\n").writerow(
                    [entry.source, entry.target, entry.note]
                )
        elif is_json:
            data = [
                {"source": e.source, "target": e.target, **({"note": e.note} if e.note else {})}
                for e in entries
            ]
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            with path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.writer(file, lineterminator="\n")
                writer.writerow(["source", "target", "note"])
                for e in entries:
                    writer.writerow([e.source, e.target, e.note])
    except OSError as e:
        raise GlossaryError(f"Failed to write glossary file {path}: {e}") from e
    logger.info(f"Added glossary entry {entry.source!r} -> {entry.target!r} to {path}")
