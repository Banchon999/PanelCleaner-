import json
import re
from pathlib import Path
from typing import Callable

from attrs import frozen
from loguru import logger
from natsort import natsorted

import pcleaner.config as cfg
import pcleaner.structures as st
from pcleaner.translation.glossary import Glossary, GlossaryEntry
from pcleaner.translation.openrouter import OpenRouterClient, OpenRouterError

# How often to re-ask the model when its answer is missing bubbles or isn't valid JSON.
MAX_FORMAT_RETRIES = 2


class TranslationError(Exception):
    pass


@frozen
class TranslationResult:
    """
    translations: Maps each OCR analytic path to one translation per entry in its removed_box_data.
        Bubbles that failed to translate have an empty string.
    failed_pages: Paths of the pages where at least one bubble failed to translate.
    """

    translations: dict[Path, list[str]]
    failed_pages: list[Path]


def translated_output_path(ocr_output_path: Path) -> Path:
    """
    Get the path to write the translated output to, next to the OCR output.
    E.g. detected_text.csv -> detected_text_translated.csv

    :param ocr_output_path: The path of the OCR output file.
    :return: The path for the translated file.
    """
    return ocr_output_path.with_name(f"{ocr_output_path.stem}_translated{ocr_output_path.suffix}")


def load_glossary(translator_conf: cfg.TranslatorConfig) -> Glossary:
    """
    Load the glossary configured in the profile, if any.

    :param translator_conf: The translator section of the profile.
    :return: The glossary, empty if none is configured.
    :raises TranslationError: If a glossary is configured but can't be loaded.
    """
    if not translator_conf.glossary_path:
        return Glossary()
    try:
        return Glossary.load(translator_conf.glossary_path)
    except Exception as e:
        raise TranslationError(str(e)) from e


def build_system_prompt(translator_conf: cfg.TranslatorConfig) -> str:
    source = translator_conf.translation_source_language or "the original language (auto-detect)"
    target = translator_conf.translation_target_language
    prompt = (
        f"You are a professional manga and comic translator. "
        f"Translate the speech bubbles of one page from {source} into {target}.\n"
        "Rules:\n"
        "- Translate naturally and fluently, keeping each character's tone and voice. "
        "Do not translate word for word.\n"
        "- The bubbles are given in reading order and belong to the same page, "
        "use them as context for each other.\n"
        "- OCR text may contain recognition errors or broken line breaks, "
        "infer the intended meaning.\n"
        "- Keep sound effects and interjections short.\n"
        "- If a glossary is given, you MUST use its translations for those terms.\n"
        "- Do not add notes, explanations or romanization.\n"
        'Reply with JSON only, in the form {"translations": [{"id": 1, "text": "..."}]}, '
        "with exactly one entry for every bubble id you were given."
    )
    if translator_conf.translation_instructions.strip():
        prompt += (
            "\n\nAdditional instructions:\n" + translator_conf.translation_instructions.strip()
        )
    return prompt


def build_user_prompt(
    page_name: str,
    texts: list[str],
    glossary_matches: list[GlossaryEntry],
    previous_context: list[tuple[str, str]],
) -> str:
    payload: dict = {"page": page_name}
    if glossary_matches:
        payload["glossary"] = [
            {"source": e.source, "target": e.target, **({"note": e.note} if e.note else {})}
            for e in glossary_matches
        ]
    if previous_context:
        payload["previous_page_context"] = [
            {"source": src, "translation": tgt} for src, tgt in previous_context
        ]
    payload["bubbles"] = [{"id": i, "text": text} for i, text in enumerate(texts, start=1)]
    return json.dumps(payload, ensure_ascii=False, indent=1)


def parse_response(raw: str, expected_count: int) -> dict[int, str]:
    """
    Extract the translations from the model's reply.
    Tolerates markdown code fences and text around the JSON object.

    :param raw: The raw reply text.
    :param expected_count: The number of bubbles that were sent.
    :return: A mapping of bubble id (1-based) to translation. May be incomplete.
    :raises ValueError: If no valid JSON could be found.
    """
    text = raw.strip()
    # Strip markdown code fences.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # Cut down to the outermost JSON object.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in reply: {raw[:200]}")
    data = json.loads(text[start : end + 1])

    items = data.get("translations") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError(f"Reply has no 'translations' list: {raw[:200]}")

    result: dict[int, str] = {}
    for index, item in enumerate(items, start=1):
        if isinstance(item, dict):
            try:
                bubble_id = int(item.get("id", index))
            except (TypeError, ValueError):
                bubble_id = index
            value = item.get("text", "")
        else:
            # Some models reply with a plain list of strings.
            bubble_id, value = index, item
        if 1 <= bubble_id <= expected_count and isinstance(value, str):
            result[bubble_id] = value.strip()
    return result


def translate_page(
    client: OpenRouterClient,
    system_prompt: str,
    page_name: str,
    texts: list[str],
    glossary: Glossary,
    previous_context: list[tuple[str, str]],
) -> tuple[list[str], bool]:
    """
    Translate all bubbles of one page in a single request.

    :param client: The OpenRouter client.
    :param system_prompt: The system prompt.
    :param page_name: The page name, given to the model for context.
    :param texts: The bubble texts. Empty texts are skipped.
    :param glossary: The glossary.
    :param previous_context: (source, translation) pairs from the previous page.
    :return: The translations in the same order as the texts, and whether all succeeded.
    """
    # Only send bubbles that actually contain text.
    to_send = [(i, t.strip()) for i, t in enumerate(texts) if t.strip()]
    translations = [""] * len(texts)
    if not to_send:
        return translations, True

    send_texts = [t for _, t in to_send]
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": build_user_prompt(
                page_name, send_texts, glossary.find_matches(send_texts), previous_context
            ),
        },
    ]

    parsed: dict[int, str] = {}
    for attempt in range(MAX_FORMAT_RETRIES + 1):
        raw = client.chat(messages, json_mode=True)
        try:
            parsed = parse_response(raw, len(send_texts))
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Invalid translation reply for {page_name}: {e}")
            parsed = {}
        if len(parsed) == len(send_texts):
            break
        logger.warning(
            f"Got {len(parsed)}/{len(send_texts)} translations for {page_name} "
            f"(attempt {attempt + 1})."
        )
        messages = messages[:2] + [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": f"Your reply must be valid JSON with exactly {len(send_texts)} "
                f"entries, ids 1 to {len(send_texts)}. Reply again with the full JSON only.",
            },
        ]

    for bubble_id, (original_index, _) in enumerate(to_send, start=1):
        translations[original_index] = parsed.get(bubble_id, "")
    return translations, len(parsed) == len(send_texts)


def create_client(translator_conf: cfg.TranslatorConfig, api_key: str | None) -> OpenRouterClient:
    """
    Create the OpenRouter client for the configured model.

    :param translator_conf: The translator section of the profile.
    :param api_key: The OpenRouter API key.
    :return: The client.
    :raises TranslationError: If the API key or model is missing.
    """
    try:
        return OpenRouterClient(
            api_key,
            translator_conf.translation_model,
            translator_conf.translation_temperature,
        )
    except OpenRouterError as e:
        raise TranslationError(str(e)) from e


def retranslate_page(
    translator_conf: cfg.TranslatorConfig,
    api_key: str | None,
    page_name: str,
    texts: list[str],
    previous_context: list[tuple[str, str]],
) -> list[str]:
    """
    Translate a single page again, e.g. from the review window.
    The glossary is reloaded, so terms added in the meantime are used.

    :param translator_conf: The translator section of the profile.
    :param api_key: The OpenRouter API key.
    :param page_name: The page name, given to the model for context.
    :param texts: The bubble texts of the page.
    :param previous_context: (source, translation) pairs from the previous page.
    :return: The translations in the same order as the texts.
    :raises TranslationError: If the translation failed, or was incomplete.
    """
    glossary = load_glossary(translator_conf)
    client = create_client(translator_conf, api_key)
    try:
        translations, complete = translate_page(
            client,
            build_system_prompt(translator_conf),
            page_name,
            texts,
            glossary,
            (
                previous_context[-translator_conf.translation_context_lines :]
                if translator_conf.translation_context_lines > 0
                else []
            ),
        )
    except OpenRouterError as e:
        raise TranslationError(str(e)) from e
    if not complete:
        raise TranslationError("The model didn't return a translation for every bubble.")
    return translations


def translate_ocr_analytics(
    ocr_analytics: list[st.OCRAnalytic],
    translator_conf: cfg.TranslatorConfig,
    api_key: str | None,
    progress_callback: Callable[[int, int], None] | None = None,
    abort_check: Callable[[], None] | None = None,
) -> TranslationResult:
    """
    Translate the OCR output of all pages, one request per page.
    Pages are processed in natural sort order so the previous page context makes sense.

    :param ocr_analytics: The OCR results.
    :param translator_conf: The translator section of the profile.
    :param api_key: The OpenRouter API key.
    :param progress_callback: [Optional] Called with (pages done, total pages) after each page.
    :param abort_check: [Optional] Called before each page, may raise to abort.
    :return: The translations.
    :raises TranslationError: If the setup is invalid or the API rejects the request.
    """
    glossary = load_glossary(translator_conf)
    client = create_client(translator_conf, api_key)

    system_prompt = build_system_prompt(translator_conf)
    translations: dict[Path, list[str]] = {}
    failed_pages: list[Path] = []
    previous_context: list[tuple[str, str]] = []

    pages = natsorted(ocr_analytics, key=lambda a: str(a.path))
    for done, analytic in enumerate(pages):
        if abort_check is not None:
            abort_check()
        texts = [text for text, _ in analytic.removed_box_data]
        page_name = Path(analytic.path).name
        try:
            page_translations, complete = translate_page(
                client, system_prompt, page_name, texts, glossary, previous_context
            )
        except OpenRouterError as e:
            # Authentication and similar errors will fail for every page, so stop right away.
            if not translations and not failed_pages:
                raise TranslationError(str(e)) from e
            logger.error(f"Failed to translate {page_name}: {e}")
            page_translations, complete = [""] * len(texts), False

        translations[analytic.path] = page_translations
        if not complete:
            failed_pages.append(analytic.path)

        if translator_conf.translation_context_lines > 0:
            pairs = [(s, t) for s, t in zip(texts, page_translations) if s.strip() and t]
            previous_context = pairs[-translator_conf.translation_context_lines :]

        if progress_callback is not None:
            progress_callback(done + 1, len(pages))

    return TranslationResult(translations, failed_pages)
