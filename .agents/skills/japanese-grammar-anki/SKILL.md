---
name: japanese-grammar-anki
description: "Preview Japanese grammar questions and translation corrections as Anki cards and import them through AnkiConnect only after explicit user confirmation."
metadata:
  short-description: "预览日语语法题并安全导入 Anki"
---

# Japanese Grammar Anki Cards

Create Anki cards from Japanese grammar exercise screenshots. The user normally sends an image and an explicit instruction such as “制卡”“加入 Anki” or “导入 Anki”.

## Hard boundaries

- Always show a card preview first and wait for explicit confirmation such as “确认导入”. Do not import in the same turn merely because the initial message asked to make a card.
- Import only into `日语::语法`. Do not create, move, rename, or modify other decks.
- Do not embed or upload the screenshot. Keep the hidden `截图` field empty so the workflow can be extended later.
- If any question is blurry, incomplete, or has multiple plausible answers, pause and ask the user before previewing a final card or importing.
- Do not silently correct uncertain source text. Label any unavoidable assumption in the preview.
- Do not treat a confirmation for one preview as confirmation for later cards.
- For translation corrections, the front must show both the Chinese source and the user's original translation. The corrected translation, corrections, and grammar summary belong on the back.

## Workflow

1. Read the screenshot and identify each independent question. For multiple questions, preview one note per question, ordered as they appear.
2. Solve the question and select the display shape that fits it. Grammar choice questions include options; fill-in and correction questions hide the answer until the back.
3. Build one JSON payload per note. Keep Japanese source text exact, provide concise Chinese explanations, and name the tested grammar point.
4. Run the read-only preview command:

   ```bash
   python3 scripts/anki_cards.py preview --payload-file /tmp/anki-card.json
   ```

5. Present the preview to the user with these labels:
   - 题型
   - 正面
   - 原译，when the user supplied one
   - 选项，if present
   - 答案
   - 解析
   - 语法点
   - 标签
   - 重复检查
   - 目标牌组 `日语::语法`
6. Stop. Import only after the user confirms that preview.
7. After confirmation, run:

   ```bash
   python3 scripts/anki_cards.py add --payload-file /tmp/anki-card.json --user-confirmed
   ```

   Run this once per confirmed note.
8. Report every Anki note ID. If duplicate detection blocks a note, report the existing note ID and wait for direction.

## Payload

Use English keys for the script:

```json
{
  "type": "语法选择",
  "stem": "彼は疲れている＿＿＿、早く寝た。",
  "original_translation": "",
  "options": ["ので", "のに", "ながら", "ため"],
  "answer": "ので",
  "explanation": "「疲れている」表示原因，因此接续「ので」，表示因为累了所以早睡了。",
  "grammar_points": ["〜ので：表示原因、理由"],
  "examples": ["雨が降っているので、試合は中止です。"],
  "notes": "",
  "tags": ["JLPT-N4"]
}
```

Required keys are `type`, `stem`, `answer`, and `explanation`. `original_translation` is required for `翻译纠错` cards and appears on the front. The script adds `日语语法` and `截图制卡` tags. It derives a hidden duplicate key from the normalized question, original translation, options, and answer.

## Commands

- `python3 scripts/anki_cards.py status`: read-only connection and structure check.
- `python3 scripts/anki_cards.py setup --user-confirmed`: idempotently create `日语`, `日语::语法`, and the `日语语法题` note type.
- `python3 scripts/anki_cards.py preview --payload-file PATH`: read-only preview and duplicate check.
- `python3 scripts/anki_cards.py add --payload-file PATH --user-confirmed`: add one already-confirmed note.

AnkiConnect must be listening at `http://127.0.0.1:8765`. If it is unavailable, tell the user to open Anki and confirm that AnkiConnect is enabled; do not edit the AnkiConnect configuration automatically.
