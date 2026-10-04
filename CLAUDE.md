# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

Panel Cleaner (`pcleaner`): a Python desktop/CLI tool that detects text in manga/comic pages,
builds masks to cover it, optionally denoises and inpaints (LaMa), and can run OCR to extract text.
GUI is PySide6 (Qt); CLI uses docopt. License GPL-3.0.

## Commands

All tooling is driven by the `Makefile` and uv dependency groups in `pyproject.toml`.

- Create CPU dev env: `make uv-sync-gui-cpu` (creates `.venv-gui-cpu`, Python 3.14 by default)
- Run GUI: `make run-gui-cpu` or `python -m pcleaner.gui.launcher`
- Run CLI: `python -m pcleaner.main <subcommand>` (see docstring at top of `pcleaner/main.py`)
- Tests: `python -m pytest tests/`
- Format: `make black-format` (black, line length 100; excludes `pcleaner/gui/ui_generated_files/` and `pcleaner/comic_text_detector/`)
- Rebuild Qt UI code after editing `ui_files/*.ui`: `make compile-ui`
- Translations: `make refresh-i18n` / `make compile-i18n`
- Sync `setup-cli*.cfg` from `pyproject.toml` groups: `make sync-setup-cfg` (`tools/sync_setup_cfg.py`)
- Wheels: `make build` (GUI) / `make build-cli`

Dependencies: add them to the uv groups in `pyproject.toml` (source of truth), then run the
setup.cfg sync. `requirements.txt` is a legacy flat list; keep it in step.

## Architecture

Processing pipeline (`pcleaner/output_structures.py: Step`), each step caching results to JSON + images
in the cache dir:

1. **text_detection** – `ctd_interface.py` wraps `comic_text_detector/` (vendored, don't reformat).
2. **preprocessor** – `preprocessor.py`: filters/merges boxes, maps languages, and optionally runs OCR
   per box (to drop symbol-only bubbles or to produce OCR output).
3. **masker** – `masker.py` + `image_ops.py`: picks the best-fitting mask per bubble.
4. **denoiser** – `denoiser.py`: denoises around tight masks.
5. **inpainter** – `inpainting.py`: `InpaintingModel` wraps `simple_lama_inpainting`; `inpaint_page()`
   decides which boxes need inpainting and composites the result.
6. **output** – `image_export.py` (PNG/PSD/etc.).

Orchestration lives in two places that must be kept in sync when the pipeline changes:
- CLI: `pcleaner/main.py`
- GUI: `pcleaner/gui/processing.py` (run from `gui/worker_thread.py`)

### OCR (`pcleaner/ocr/`)
- `ocr.py`: `OCRModel` protocol (`__call__(img_or_path, **kwargs) -> str`), `ocr_engines()`,
  and `build_ocr_engine_factory()` which returns a `LanguageCode -> OCRModel` closure.
- Engines: `ocr_mangaocr.py` (Japanese, singleton), `ocr_tesseract.py` (other languages).
- `supported_languages.py`: `LanguageCode` enum.
- Output formatting (plain text / CSV) is in `ocr.py: format_output*`; parsing back in `parsers.py`.

### Config
- `config.py`: `Config` (app-wide, stored in user config dir) and `Profile` (per-preset settings:
  `General`, `TextDetector`, `Preprocessor`, `Masker`, `Denoiser`, `Inpainter` sections).
  Each section is an attrs class with `export_to_conf()` (writes an INI section with comments,
  `[CLI: ...]` / `[GUI: ...]` markers) and `import_from_conf()` (`try_to_load`).
- Enums used as options (e.g. `OCREngine`) are `StrEnum`s; the GUI profile editor
  (`gui/profile_parser.py`) builds widgets from the field types, so a new enum option also needs an
  `EntryTypes` entry and translated labels there.
- Model downloads/paths: `model_downloader.py`.

### GUI (`pcleaner/gui/`)
- `mainwindow_driver.py` is the main window; `*_driver.py` files drive dialogs defined in `ui_files/`.
- `ui_generated_files/` and `rc_generated_files/` are generated — edit `.ui` files and regenerate.
- User-facing strings go through `self.tr(...)` for Crowdin translations (`translations/`).

## Conventions
- Python ≥ 3.10, type hints, `loguru` for logging, reST-style docstrings (`:param x:` / `:return:`).
- Don't edit vendored `pcleaner/comic_text_detector/` or generated UI files by hand.
- Keep offline-first behavior: anything network-based must be optional.
