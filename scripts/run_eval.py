"""Eval: classification accuracy + field accuracy (mock extractor)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models.document import DocumentType
from app.services.classifier import classify_document
from app.services.extractors.mock import MockEntityExtractor

CASES_PATH = ROOT / "eval" / "gold" / "cases.jsonl"

FIELD_PATHS = (
    ("patient.full_name", ("patient", "full_name")),
    ("diagnosis.code", ("diagnosis", "code")),
    ("treatment.medication", ("treatment", "medication")),
)


def load_cases(path: Path) -> list[dict]:
    """Читает JSON-массив, pretty-объекты подряд или классический JSONL."""
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    first = json.loads(raw)
    if isinstance(first, list):
        return first
    if isinstance(first, dict):
        return [first]

    decoder = json.JSONDecoder()
    idx = 0
    cases: list[dict] = []
    while idx < len(raw):
        while idx < len(raw) and raw[idx].isspace():
            idx += 1
        if idx >= len(raw):
            break
        obj, end = decoder.raw_decode(raw, idx)
        cases.append(obj)
        idx = end
    return cases


def dig(data: dict | None, path: tuple[str, ...]):
    cur = data
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def norm(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value).strip().casefold()


def main() -> None:
    cases = load_cases(CASES_PATH)
    if not cases:
        raise SystemExit(f"No cases in {CASES_PATH}")

    extractor = MockEntityExtractor()

    type_ok = 0
    field_ok = 0
    field_total = 0
    field_stats = {name: {"ok": 0, "total": 0} for name, _ in FIELD_PATHS}

    print(f"Loaded {len(cases)} cases from {CASES_PATH}")
    print("-" * 60)

    for case in cases:
        case_id = case["id"]
        text = case["text"]
        expected_type = case["expected_type"]
        expected = case.get("expected") or {}

        pred_type = classify_document(text).value
        type_match = pred_type == expected_type
        type_ok += int(type_match)

        # поля считаем относительно gold-типа (изолируем extraction от classification)
        result = extractor.extract(text, DocumentType(expected_type))
        data = result.data

        miss = []
        for name, path in FIELD_PATHS:
            if expected.get(path[0]) is None:
                continue
            exp_val = dig(expected, path)
            if exp_val is None:
                continue

            field_total += 1
            field_stats[name]["total"] += 1
            pred_val = dig(data, path)
            match = norm(pred_val) == norm(exp_val)
            if match:
                field_ok += 1
                field_stats[name]["ok"] += 1
            else:
                miss.append(f"{name}: got={pred_val!r} exp={exp_val!r}")

        mark = "OK" if type_match and not miss else ".."
        print(f"[{mark}] {case_id}: type {pred_type} (exp {expected_type})")
        for line in miss:
            print(f"       {line}")

    print("-" * 60)
    print(f"Classification accuracy: {type_ok}/{len(cases)} = {type_ok / len(cases):.3f}")
    if field_total:
        print(f"Field accuracy (micro): {field_ok}/{field_total} = {field_ok / field_total:.3f}")
        for name, st in field_stats.items():
            if st["total"]:
                print(
                    f"  - {name}: {st['ok']}/{st['total']} = {st['ok'] / st['total']:.3f}"
                )
    else:
        print("Field accuracy: n/a (no expected fields)")


if __name__ == "__main__":
    main()