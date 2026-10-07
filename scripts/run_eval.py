"""Eval: classification accuracy + field accuracy (mock extractor)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models.document import DocumentType  # noqa: E402
from app.services.classifier import classify_document  # noqa: E402
from app.services.extractors.mock import MockEntityExtractor  # noqa: E402

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
    parser = argparse.ArgumentParser(description="DocMind eval")
    parser.add_argument(
        "--provider",
        choices=("mock", "llm"),
        default="mock",
        help="mock или llm",
    )
    parser.add_argument(
        "--out",
        default="",
        help="куда сохранить JSON с метриками, например eval/results/llm_bad.json",
    )
    args = parser.parse_args()

    cases = load_cases(CASES_PATH)
    if not cases:
        raise SystemExit(f"No cases in {CASES_PATH}")

    if args.provider == "mock":
        extractor = MockEntityExtractor()
    else:
        from app.services.extractors.llm import LlmEntityExtractor

        extractor = LlmEntityExtractor()

    type_ok = 0
    field_ok = 0
    field_total = 0
    field_stats = {name: {"ok": 0, "total": 0} for name, _ in FIELD_PATHS}

    print(f"Provider: {args.provider}")
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

        miss = []
        try:
            result = extractor.extract(text, DocumentType(expected_type))
            data = result.data
        except Exception as exc:
            print(f"[ERR] {case_id}: extract failed: {exc}")
            data = {}
            for name, path in FIELD_PATHS:
                if expected.get(path[0]) is None:
                    continue
                exp_val = dig(expected, path)
                if exp_val is None:
                    continue
                field_total += 1
                field_stats[name]["total"] += 1
                miss.append(f"{name}: extract_error")
            mark = ".."
            print(f"[{mark}] {case_id}: type {pred_type} (exp {expected_type})")
            for line in miss:
                print(f"       {line}")
            continue

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

    summary = {
        "provider": args.provider,
        "cases": len(cases),
        "classification_ok": type_ok,
        "classification_accuracy": round(type_ok / len(cases), 3),
        "field_ok": field_ok,
        "field_total": field_total,
        "field_accuracy_micro": round(field_ok / field_total, 3) if field_total else None,
        "fields": {
            name: {
                "ok": st["ok"],
                "total": st["total"],
                "accuracy": round(st["ok"] / st["total"], 3) if st["total"] else None,
            }
            for name, st in field_stats.items()
            if st["total"]
        },
    }

    print("-" * 60)
    print(
        f"Classification accuracy: {type_ok}/{len(cases)} = "
        f"{summary['classification_accuracy']:.3f}"
    )
    if field_total:
        print(
            f"Field accuracy (micro): {field_ok}/{field_total} = "
            f"{summary['field_accuracy_micro']:.3f}"
        )
        for name, st in summary["fields"].items():
            print(f"  - {name}: {st['ok']}/{st['total']} = {st['accuracy']:.3f}")
    else:
        print("Field accuracy: n/a (no expected fields)")

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
