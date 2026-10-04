import json
from pathlib import Path

import pytest

import pcleaner.config as cfg
import pcleaner.ocr.ocr as ocr
import pcleaner.ocr.parsers as op
import pcleaner.structures as st
import pcleaner.translation.openrouter as orc
import pcleaner.translation.translator as trl
from pcleaner.translation.glossary import Glossary, GlossaryEntry, GlossaryError


class FakeClient:
    """
    Stands in for the OpenRouterClient, replying with queued answers
    or translating every bubble by tagging it.
    """

    def __init__(self, replies: list[str] | None = None) -> None:
        self.replies = list(replies or [])
        self.requests: list[list[dict[str, str]]] = []

    def chat(self, messages, json_mode=False) -> str:
        self.requests.append(messages)
        if self.replies:
            return self.replies.pop(0)
        bubbles = json.loads(messages[1]["content"])["bubbles"]
        return json.dumps(
            {"translations": [{"id": b["id"], "text": f"T:{b['text']}"} for b in bubbles]}
        )


def make_analytic(path: str, texts: list[str]) -> st.OCRAnalytic:
    boxes = [(text, st.Box(i, i, i + 10, i + 10)) for i, text in enumerate(texts)]
    return st.OCRAnalytic(Path(path), len(texts), [], [], boxes)


# ================================ Glossary ================================


def test_glossary_csv_with_header_bom_and_notes(tmp_path):
    path = tmp_path / "glossary.csv"
    path.write_text(
        "﻿source,target,note\n"
        "ルフィ,Luffy,main character\n"
        "\n"
        "# a comment\n"
        'ゾロ,Zoro,"swordsman, lost"\n'
        "missing\n",
        encoding="utf-8",
    )
    glossary = Glossary.load(path)
    assert len(glossary) == 2
    assert GlossaryEntry("ゾロ", "Zoro", "swordsman, lost") in glossary.entries


def test_glossary_csv_without_header(tmp_path):
    path = tmp_path / "glossary.csv"
    path.write_text("ルフィ,Luffy\n", encoding="utf-8")
    assert Glossary.load(path).entries == [GlossaryEntry("ルフィ", "Luffy")]


def test_glossary_json_formats(tmp_path):
    mapping = tmp_path / "a.json"
    mapping.write_text(json.dumps({"ルフィ": "Luffy"}), encoding="utf-8")
    assert Glossary.load(mapping).entries == [GlossaryEntry("ルフィ", "Luffy")]

    listing = tmp_path / "b.json"
    listing.write_text(
        json.dumps([{"source": "ゾロ", "target": "Zoro", "note": "swordsman"}]), encoding="utf-8"
    )
    assert Glossary.load(listing).entries == [GlossaryEntry("ゾロ", "Zoro", "swordsman")]

    bad = tmp_path / "c.json"
    bad.write_text(json.dumps([{"source": "x"}]), encoding="utf-8")
    with pytest.raises(GlossaryError):
        Glossary.load(bad)


def test_glossary_missing_file(tmp_path):
    with pytest.raises(GlossaryError):
        Glossary.load(tmp_path / "nope.csv")


def test_glossary_matches_case_insensitive_longest_first():
    glossary = Glossary(
        [
            GlossaryEntry("Gomu", "Rubber"),
            GlossaryEntry("Gomu Gomu no", "Gum-Gum"),
            GlossaryEntry("Zoro", "Zolo"),
        ]
    )
    matches = glossary.find_matches(["GOMU GOMU NO pistol!"])
    assert [m.source for m in matches] == ["Gomu Gomu no", "Gomu"]


# ================================ Prompt and reply handling ================================


def test_parse_response_handles_fences_and_plain_lists():
    reply = (
        'Sure:\n```json\n{"translations": [{"id": 2, "text": " b "}, {"id": 1, "text": "a"}]}\n```'
    )
    assert trl.parse_response(reply, 2) == {1: "a", 2: "b"}
    assert trl.parse_response('{"translations": ["x", "y"]}', 2) == {1: "x", 2: "y"}
    # Ids out of range are dropped.
    assert trl.parse_response('{"translations": [{"id": 5, "text": "x"}]}', 2) == {}
    with pytest.raises(ValueError):
        trl.parse_response("no json here", 1)


def test_translate_page_skips_empty_bubbles_and_sends_glossary():
    client = FakeClient()
    glossary = Glossary([GlossaryEntry("ルフィ", "Luffy"), GlossaryEntry("ナミ", "Nami")])
    translations, complete = trl.translate_page(
        client, "system", "p1.jpg", ["ルフィ!", "  ", "hi"], glossary, []
    )
    assert complete
    assert translations == ["T:ルフィ!", "", "T:hi"]
    payload = json.loads(client.requests[0][1]["content"])
    assert payload["glossary"] == [{"source": "ルフィ", "target": "Luffy"}]
    assert len(payload["bubbles"]) == 2


def test_translate_page_retries_incomplete_reply():
    client = FakeClient(['{"translations": [{"id": 1, "text": "a"}]}'])
    translations, complete = trl.translate_page(
        client, "system", "p1.jpg", ["x", "y"], Glossary(), []
    )
    assert complete
    assert translations == ["T:x", "T:y"]
    # The retry includes the bad reply and a correction request.
    assert len(client.requests) == 2
    assert client.requests[1][2]["role"] == "assistant"


def test_translate_page_gives_up_after_retries():
    bad = '{"translations": []}'
    client = FakeClient([bad] * (trl.MAX_FORMAT_RETRIES + 1))
    translations, complete = trl.translate_page(client, "system", "p1.jpg", ["x"], Glossary(), [])
    assert not complete
    assert translations == [""]


def test_system_prompt_contains_settings():
    conf = cfg.TranslatorConfig(
        translation_target_language="Thai",
        translation_source_language="Japanese",
        translation_instructions="Keep honorifics.",
    )
    prompt = trl.build_system_prompt(conf)
    assert "from Japanese into Thai" in prompt
    assert "Keep honorifics." in prompt


# ================================ Whole batch ================================


def test_translate_ocr_analytics_orders_pages_and_passes_context(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(trl, "OpenRouterClient", lambda *args, **kwargs: client)
    conf = cfg.TranslatorConfig(translation_context_lines=1)
    analytics = [make_analytic("p10.jpg", ["c"]), make_analytic("p2.jpg", ["a", "b"])]
    progress = []

    result = trl.translate_ocr_analytics(
        analytics, conf, "key", progress_callback=lambda d, t: progress.append((d, t))
    )

    assert result.translations == {Path("p2.jpg"): ["T:a", "T:b"], Path("p10.jpg"): ["T:c"]}
    assert result.failed_pages == []
    assert progress == [(1, 2), (2, 2)]
    # Natural sort: p2 before p10, and p10 gets the last line of p2 as context.
    second = json.loads(client.requests[1][1]["content"])
    assert second["page"] == "p10.jpg"
    assert second["previous_page_context"] == [{"source": "b", "translation": "T:b"}]


def test_translate_ocr_analytics_errors():
    conf = cfg.TranslatorConfig()
    with pytest.raises(trl.TranslationError):
        trl.translate_ocr_analytics([make_analytic("p1.jpg", ["a"])], conf, None)

    conf = cfg.TranslatorConfig(glossary_path="/does/not/exist.csv")
    with pytest.raises(trl.TranslationError):
        trl.translate_ocr_analytics([make_analytic("p1.jpg", ["a"])], conf, "key")


def test_translate_ocr_analytics_first_page_api_error_aborts(monkeypatch):
    class FailingClient(FakeClient):
        def chat(self, messages, json_mode=False):
            raise orc.OpenRouterError("401 unauthorized")

    monkeypatch.setattr(trl, "OpenRouterClient", lambda *args, **kwargs: FailingClient())
    with pytest.raises(trl.TranslationError):
        trl.translate_ocr_analytics([make_analytic("p1.jpg", ["a"])], cfg.TranslatorConfig(), "key")


def test_resolve_api_key_prefers_environment(monkeypatch):
    monkeypatch.delenv(orc.API_KEY_ENV_VAR, raising=False)
    assert orc.resolve_api_key(None) is None
    assert orc.resolve_api_key(" cfg ") == "cfg"
    monkeypatch.setenv(orc.API_KEY_ENV_VAR, "env")
    assert orc.resolve_api_key("cfg") == "env"


def test_translated_output_path():
    assert trl.translated_output_path(Path("/a/detected_text.csv")) == Path(
        "/a/detected_text_translated.csv"
    )


# ================================ Output and parsing ================================


def test_translated_output_round_trips_through_parsers(tmp_path):
    analytics = [make_analytic("/x/p1.jpg", ["a", "b,c"]), make_analytic("/x/p2.jpg", ["d"])]
    translations = {Path("/x/p1.jpg"): ["A", "B, C"], Path("/x/p2.jpg"): ["D"]}
    columns = ("filename", "startx", "starty", "endx", "endy", "text", "translation")

    csv_text = ocr.format_output(analytics, True, columns, translations=translations)
    assert csv_text.splitlines()[0] == ",".join(columns)
    assert csv_text.splitlines()[2] == 'p1.jpg,1,1,11,11,"b,c","B, C"'
    csv_path = tmp_path / "out.csv"
    csv_path.write_text(csv_text, encoding="utf-8")
    parsed, errors = op.parse_ocr_data(csv_path)
    assert not errors
    assert [t for t, _ in parsed[0].removed_box_data] == ["a", "b,c"]

    plain_text = ocr.format_output(analytics, False, columns, translations=translations)
    assert "\na\n→ A\nb,c\n→ B, C" in plain_text
    txt_path = tmp_path / "out.txt"
    txt_path.write_text(plain_text.strip(), encoding="utf-8")
    parsed, errors = op.parse_ocr_data(txt_path)
    assert not errors
    assert [t for t, _ in parsed[0].removed_box_data] == ["a", "b,c"]
    assert [t for t, _ in parsed[1].removed_box_data] == ["d"]


def test_output_without_translations_is_unchanged():
    analytics = [make_analytic("p1.jpg", ["a"])]
    columns = ("filename", "startx", "starty", "endx", "endy", "text")
    assert ocr.format_output(analytics, True, columns).splitlines() == [
        ",".join(columns),
        "p1.jpg,0,0,10,10,a",
    ]
    assert "→" not in ocr.format_output(analytics, False, columns)


# ================================ Profile ================================


def test_translator_profile_round_trip(tmp_path):
    profile = cfg.Profile()
    profile.translator.translation_enabled = True
    profile.translator.translation_target_language = "Thai"
    profile.translator.glossary_path = "/g.csv"
    profile.translator.translation_instructions = "line 1\nline 2"
    path = tmp_path / "profile.conf"
    assert profile.safe_write(path)

    loaded = cfg.Profile.load(path)
    assert loaded.translator == profile.translator


def test_translator_fix_clamps_values():
    conf = cfg.TranslatorConfig(
        translation_temperature=5, translation_context_lines=-3, translation_target_language=" "
    )
    conf.fix()
    assert conf.translation_temperature == 2
    assert conf.translation_context_lines == 0
    assert conf.translation_target_language == "English"
