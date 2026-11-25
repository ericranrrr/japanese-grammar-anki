#!/usr/bin/env python3
"""Preview and import Japanese grammar cards through AnkiConnect."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ENDPOINT = os.environ.get("ANKI_CONNECT_URL", "http://127.0.0.1:8765")
DECK = "日语::语法"
PARENT_DECK = "日语"
MODEL = "日语语法题"
TIMEOUT_SECONDS = 8

FIELDS = [
    "题型",
    "题干",
    "原译",
    "选项",
    "答案",
    "解析",
    "语法点",
    "例句",
    "补充说明",
    "截图",
    "去重键",
]

CSS = """
.card {
  width: min(100%, 46rem);
  margin: 0 auto;
  color: #202124;
  background: #fffdf8;
  font-family: "Hiragino Mincho ProN", "Yu Mincho", "Noto Serif CJK JP", serif;
  font-size: 1.08rem;
  line-height: 1.75;
  text-align: left;
}

.type {
  display: inline-block;
  margin-bottom: 1rem;
  padding: 0.12rem 0.7rem;
  border-radius: 999px;
  color: #5d4037;
  background: #f1e7dc;
  font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", sans-serif;
  font-size: 0.82rem;
}

.stem, .options {
  margin: 0.7rem 0;
  font-size: 1.18rem;
}

.translation-block {
  margin: 1rem 0;
  padding: 0.75rem 0.9rem;
  border-left: 4px solid #cdbba9;
  border-radius: 0 8px 8px 0;
  background: #f8f2eb;
}

.original {
  color: #4a4038;
  font-size: 1.08rem;
}

.option {
  margin: 0.35rem 0;
  padding: 0.5rem 0.75rem;
  border: 1px solid #ddd3c8;
  border-radius: 8px;
  background: #fff;
}

hr#answer {
  margin: 1.4rem 0 1rem;
  border: 0;
  border-top: 1px solid #d8cfc5;
}

.section {
  margin: 1rem 0;
}

.label {
  margin-bottom: 0.18rem;
  color: #7b6655;
  font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", sans-serif;
  font-size: 0.82rem;
  letter-spacing: 0.08em;
}

.answer {
  color: #8a3b12;
  font-size: 1.28rem;
  font-weight: 700;
}

.grammar, .examples {
  margin: 0.35rem 0 0;
  padding-left: 1.25rem;
}

.notes {
  color: #5f6368;
}

.nightMode .card {
  color: #eceff1;
  background: #202124;
}

.nightMode .option {
  border-color: #4a4d50;
  background: #292a2d;
}

.nightMode .translation-block {
  border-left-color: #8d735f;
  background: #2b2926;
}

.nightMode .original {
  color: #e2d9d0;
}

.nightMode .type {
  color: #ffccb3;
  background: #4b352b;
}

.nightMode .label, .nightMode .notes {
  color: #b0bec5;
}

.nightMode .answer {
  color: #ffab76;
}
"""

FRONT = """
<div class="question">
  {{#题型}}<div class="type">{{题型}}</div>{{/题型}}
  <div class="stem">{{题干}}</div>
  {{#原译}}
  <div class="translation-block">
    <div class="label">我的翻译</div>
    <div class="original">{{原译}}</div>
  </div>
  {{/原译}}
  {{#选项}}<div class="options">{{选项}}</div>{{/选项}}
</div>
"""

BACK = """
{{FrontSide}}
<hr id="answer">
<div class="section">
  <div class="label">修正译文 / 答案</div>
  <div class="answer">{{答案}}</div>
</div>
<div class="section">
  <div class="label">解析 / 纠错</div>
  <div>{{解析}}</div>
</div>
{{#语法点}}
<div class="section">
  <div class="label">语法点</div>
  <ul class="grammar">{{语法点}}</ul>
</div>
{{/语法点}}
{{#例句}}
<div class="section">
  <div class="label">例句</div>
  <ul class="examples">{{例句}}</ul>
</div>
{{/例句}}
{{#补充说明}}
<div class="section notes">
  <div class="label">补充说明</div>
  <div>{{补充说明}}</div>
</div>
{{/补充说明}}
"""


class AnkiError(RuntimeError):
    """Base error for actionable AnkiConnect failures."""


class ConnectionFailure(AnkiError):
    """AnkiConnect is not reachable."""


class DuplicateCard(AnkiError):
    """A note with the same duplicate key already exists."""


def invoke(action: str, **params: Any) -> Any:
    body = json.dumps(
        {"action": action, "version": 6, "params": params},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionFailure(
            f"无法连接 AnkiConnect（{ENDPOINT}）。请打开 Anki 并确认 AnkiConnect 已启用。原始错误：{exc}"
        ) from exc

    if payload.get("error"):
        raise AnkiError(f"AnkiConnect 返回错误：{payload['error']}")
    return payload.get("result")


def status() -> dict[str, Any]:
    version = invoke("version")
    decks = invoke("deckNames")
    models = invoke("modelNames")
    model_state: dict[str, Any] = {"exists": MODEL in models}
    if MODEL in models:
        model_state["fields"] = invoke("modelFieldNames", modelName=MODEL)
        model_state["templates"] = list(
            invoke("modelTemplates", modelName=MODEL).keys()
        )
    return {
        "connected": True,
        "endpoint": ENDPOINT,
        "version": version,
        "target_deck": DECK,
        "deck_exists": DECK in decks,
        "parent_deck_exists": PARENT_DECK in decks,
        "model": MODEL,
        "model_state": model_state,
    }


def ensure_setup() -> dict[str, Any]:
    decks_before = set(invoke("deckNames"))
    created_decks = []
    for deck in (PARENT_DECK, DECK):
        if deck not in decks_before:
            invoke("createDeck", deck=deck)
            created_decks.append(deck)

    models = invoke("modelNames")
    created_model = False
    missing: list[str] = []
    if MODEL not in models:
        invoke(
            "createModel",
            modelName=MODEL,
            inOrderFields=FIELDS,
            isCloze=False,
            css=CSS,
            cardTemplates=[
                {
                    "Name": "日语语法题",
                    "Front": FRONT,
                    "Back": BACK,
                }
            ],
        )
        created_model = True
    else:
        actual_fields = invoke("modelFieldNames", modelName=MODEL)
        missing = [field for field in FIELDS if field not in actual_fields]
        for field in missing:
            invoke(
                "modelFieldAdd",
                modelName=MODEL,
                fieldName=field,
                index=FIELDS.index(field),
            )

    invoke(
        "updateModelTemplates",
        model={
            "name": MODEL,
            "templates": {
                "日语语法题": {
                    "Front": FRONT,
                    "Back": BACK,
                }
            },
        },
    )
    invoke("updateModelStyling", model={"name": MODEL, "css": CSS})

    return {
        "deck": DECK,
        "created_decks": created_decks,
        "model": MODEL,
        "created_model": created_model,
        "added_model_fields": missing,
        "updated_model_templates": True,
        "updated_model_styling": True,
        **status(),
    }


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(normalized.split()).casefold()


def rich_text(value: str) -> str:
    return html.escape(value.strip(), quote=False).replace("\n", "<br>")


def list_html(values: list[str], item_class: str | None = None) -> str:
    items = []
    for value in values:
        text = rich_text(str(value))
        if item_class:
            items.append(f'<div class="{item_class}">{text}</div>')
        else:
            items.append(f"<li>{text}</li>")
    return "".join(items)


def normalize_tags(values: Any) -> list[str]:
    tags = ["日语语法", "截图制卡"]
    if values is None:
        return tags
    if not isinstance(values, list):
        raise AnkiError("tags 必须是字符串数组。")
    for value in values:
        tag = "_".join(str(value).strip().split())
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def normalize_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AnkiError("payload 必须是 JSON 对象。")

    required = ("type", "stem", "answer", "explanation")
    missing = [
        key
        for key in required
        if not isinstance(payload.get(key), str) or not payload[key].strip()
    ]
    if missing:
        raise AnkiError(f"缺少必填字段：{', '.join(missing)}")

    options = payload.get("options", [])
    if not isinstance(options, list):
        raise AnkiError("options 必须是字符串数组。")
    options = [str(value).strip() for value in options if str(value).strip()]

    grammar_points = payload.get("grammar_points", [])
    examples = payload.get("examples", [])
    if not isinstance(grammar_points, list):
        raise AnkiError("grammar_points 必须是字符串数组。")
    if not isinstance(examples, list):
        raise AnkiError("examples 必须是字符串数组。")

    if payload.get("screenshot"):
        raise AnkiError("当前工作流不允许嵌入截图；请保持 screenshot 为空。")

    normalized = {
        "type": payload["type"].strip(),
        "stem": payload["stem"].strip(),
        "original_translation": str(
            payload.get("original_translation", "")
        ).strip(),
        "options": options,
        "answer": payload["answer"].strip(),
        "explanation": payload["explanation"].strip(),
        "grammar_points": [str(value).strip() for value in grammar_points if str(value).strip()],
        "examples": [str(value).strip() for value in examples if str(value).strip()],
        "notes": str(payload.get("notes", "")).strip(),
        "tags": normalize_tags(payload.get("tags")),
    }
    if "翻译" in normalized["type"] and not normalized["original_translation"]:
        raise AnkiError("翻译纠错卡必须提供 original_translation（用户原译）。")
    duplicate_material = json.dumps(
        {
            "type": normalize_text(normalized["type"]),
            "stem": normalize_text(normalized["stem"]),
            "original_translation": normalize_text(
                normalized["original_translation"]
            ),
            "options": [normalize_text(value) for value in normalized["options"]],
            "answer": normalize_text(normalized["answer"]),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    normalized["duplicate_key"] = hashlib.sha256(
        duplicate_material.encode("utf-8")
    ).hexdigest()
    return normalized


def fields_for(note: dict[str, Any]) -> dict[str, str]:
    return {
        "题型": rich_text(note["type"]),
        "题干": rich_text(note["stem"]),
        "原译": rich_text(note["original_translation"]),
        "选项": list_html(note["options"], "option"),
        "答案": rich_text(note["answer"]),
        "解析": rich_text(note["explanation"]),
        "语法点": list_html(note["grammar_points"]),
        "例句": list_html(note["examples"]),
        "补充说明": rich_text(note["notes"]),
        "截图": "",
        "去重键": note["duplicate_key"],
    }


def existing_note_ids(duplicate_key: str) -> list[int]:
    query = f'deck:"{DECK}" "{duplicate_key}"'
    return list(invoke("findNotes", query=query))


def note_spec(note: dict[str, Any]) -> dict[str, Any]:
    return {
        "deckName": DECK,
        "modelName": MODEL,
        "fields": fields_for(note),
        "tags": note["tags"],
        # Anki's native duplicate check uses the first field ("题型"), which is
        # intentionally repeated across cards. The hidden full-content hash in
        # existing_note_ids() performs the actual duplicate check instead.
        "options": {"allowDuplicate": True, "duplicateScope": "deck"},
    }


def preview(note: dict[str, Any]) -> dict[str, Any]:
    duplicate_ids = existing_note_ids(note["duplicate_key"])
    can_add = invoke("canAddNotes", notes=[note_spec(note)])[0]
    return {
        "目标牌组": DECK,
        "笔记类型": MODEL,
        "题型": note["type"],
        "正面": note["stem"],
        "原译": note["original_translation"],
        "选项": note["options"],
        "答案": note["answer"],
        "解析": note["explanation"],
        "语法点": note["grammar_points"],
        "例句": note["examples"],
        "补充说明": note["notes"],
        "标签": note["tags"],
        "去重键": note["duplicate_key"],
        "重复卡片ID": duplicate_ids,
        "Anki字段校验": "通过" if can_add and not duplicate_ids else "未通过",
        "写入状态": "未写入",
    }


def add_note(note: dict[str, Any]) -> dict[str, Any]:
    duplicate_ids = existing_note_ids(note["duplicate_key"])
    if duplicate_ids:
        raise DuplicateCard(
            f"发现重复卡片，未导入。现有 note ID：{', '.join(map(str, duplicate_ids))}"
        )

    note_id = invoke("addNote", note=note_spec(note))
    return {
        "写入状态": "已导入",
        "目标牌组": DECK,
        "note_id": note_id,
        "题型": note["type"],
        "去重键": note["duplicate_key"],
    }


def load_payload(args: argparse.Namespace) -> Any:
    if args.payload_file:
        return json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    if args.payload_json:
        return json.loads(args.payload_json)
    if sys.stdin.isatty():
        raise AnkiError("请通过 --payload-file、--payload-json 或标准输入提供 JSON。")
    return json.load(sys.stdin)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview and import Japanese grammar notes through AnkiConnect."
    )
    parser.add_argument(
        "--endpoint",
        default=ENDPOINT,
        help=f"AnkiConnect endpoint (default: {ENDPOINT})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="Read-only connection and structure check.")

    setup_parser = subparsers.add_parser("setup", help="Create deck and note type.")
    setup_parser.add_argument(
        "--user-confirmed",
        action="store_true",
        help="Required mutation safety flag.",
    )

    for name, help_text in (
        ("preview", "Read-only card preview and duplicate check."),
        ("add", "Add one explicitly confirmed card."),
    ):
        command = subparsers.add_parser(name, help=help_text)
        payload_group = command.add_mutually_exclusive_group()
        payload_group.add_argument("--payload-file")
        payload_group.add_argument("--payload-json")
        if name == "add":
            command.add_argument(
                "--user-confirmed",
                action="store_true",
                help="Required mutation safety flag.",
            )
    return parser


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> int:
    global ENDPOINT
    parser = build_parser()
    args = parser.parse_args()
    ENDPOINT = args.endpoint.rstrip("/")

    try:
        if args.command == "status":
            emit(status())
        elif args.command == "setup":
            if not args.user_confirmed:
                raise AnkiError("setup 需要 --user-confirmed。")
            emit(ensure_setup())
        elif args.command == "preview":
            emit(preview(normalize_payload(load_payload(args))))
        elif args.command == "add":
            if not args.user_confirmed:
                raise AnkiError("add 需要 --user-confirmed。")
            emit(add_note(normalize_payload(load_payload(args))))
        else:
            parser.error(f"未知命令：{args.command}")
    except DuplicateCard as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except AnkiError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"payload JSON 无效：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
