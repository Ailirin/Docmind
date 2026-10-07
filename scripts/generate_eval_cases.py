"""Генератор gold-кейсов для eval (200 штук)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "gold" / "cases.jsonl"

FIRST = [
    "Ivan",
    "Maria",
    "Alexey",
    "Olga",
    "Dmitry",
    "Elena",
    "Nikolai",
    "Anna",
    "Sergei",
    "Irina",
    "Pavel",
    "Vera",
    "Andrey",
    "Svetlana",
    "Kirill",
    "Natalia",
    "Maxim",
    "Yulia",
    "Roman",
    "Tatiana",
]
LAST = [
    "Petrov",
    "Sokolova",
    "Volkov",
    "Morozova",
    "Ivanov",
    "Pavlova",
    "Semenov",
    "Krylova",
    "Orlov",
    "Fomina",
    "Nikitin",
    "Titova",
    "Kuznetsov",
    "Guseva",
    "Smirnov",
    "Popova",
    "Vasiliev",
    "Novikova",
    "Mikhailov",
    "Egorova",
]
FIRST_RU = [
    "Иван",
    "Мария",
    "Алексей",
    "Ольга",
    "Дмитрий",
    "Елена",
    "Николай",
    "Анна",
    "Сергей",
    "Ирина",
    "Павел",
    "Вера",
    "Андрей",
    "Светлана",
    "Кирилл",
]
LAST_RU = [
    "Петров",
    "Соколова",
    "Волков",
    "Морозова",
    "Иванов",
    "Павлова",
    "Семёнов",
    "Крылова",
    "Орлов",
    "Фомина",
    "Никитин",
    "Титова",
    "Кузнецов",
    "Гусева",
]

# (code, name_en, name_ru)
DIAGNOSES = [
    ("J06.9", "Acute URI", "ОРВИ"),
    ("J03.9", "Acute tonsillitis", "Острый тонзиллит"),
    ("E11.9", "Type 2 diabetes", "Сахарный диабет 2 типа"),
    ("I10", "Essential hypertension", "Эссенциальная гипертензия"),
    ("N39.0", "Urinary tract infection", "Инфекция мочевых путей"),
    ("R51", "Headache NOS", "Головная боль"),
    ("K35", "Acute appendicitis", "Острый аппендицит"),
    ("I21.0", "Acute myocardial infarction", "Острый инфаркт миокарда"),
    ("J18.9", "Pneumonia", "Пневмония"),
    ("K29.7", "Gastritis, unspecified", "Гастрит"),
    ("G40.9", "Epilepsy, unspecified", "Эпилепсия"),
    ("J45.9", "Asthma, unspecified", "Астма"),
    ("M54.5", "Low back pain", "Боль в пояснице"),
    ("E03.9", "Hypothyroidism", "Гипотиреоз"),
    ("H81.1", "Benign paroxysmal vertigo", "Доброкачественное позиционное головокружение"),
]

# МНН: (medication, dosage)
INN_MEDS = [
    ("Paracetamol", "500 mg"),
    ("Metformin", "850 mg twice daily"),
    ("Amlodipine", "5 mg once daily"),
    ("Ciprofloxacin", "500 mg twice daily for 7 days"),
    ("Ibuprofen", "400 mg every 6 hours as needed"),
    ("Amoxicillin-clavulanate", "875 mg BID for 5 days"),
    ("Azithromycin", "500 mg once daily for 3 days"),
    ("Omeprazole", "20 mg OD"),
    ("Levetiracetam", "1000 mg BID"),
    ("Aspirin", "100 mg OD"),
]

# Бренды: expected = как в тексте (не МНН)
BRAND_MEDS = [
    ("Нурофен", "200 mg"),
    ("Panadol", "500 mg"),
    ("Вольтарен", "50 mg twice daily"),
    ("Омез", "20 mg OD"),
    ("Амоксиклав", "625 mg BID"),
    ("Нимесил", "100 mg BID"),
    ("Терафлю", "1 sachet TID"),
    ("Но-шпа", "40 mg TID"),
    ("Супрастин", "25 mg at night"),
    ("Эспумизан", "40 mg QID"),
]

UNKNOWN_TEXTS = [
    "Meeting notes for the cardiology department\nWeekly case review agenda.",
    "The weather is nice today. Please renew the office supplies order.",
    "Протокол собрания отдела продаж.\nОбсудили план на квартал.",
    "Shopping list: milk, bread, eggs, coffee.",
    "CI pipeline failed on step lint. Please check ruff output.",
    "Расписание тренировок: пн/ср/пт 19:00, зал 2.",
    "Invoice #4412 paid. Thank you for your business.",
    "Кот снова спит на клавиатуре. Это не медицинский документ.",
]


def name_en(i: int) -> str:
    return f"{FIRST[i % len(FIRST)]} {LAST[i % len(LAST)]}"


def name_ru(i: int) -> str:
    return f"{FIRST_RU[i % len(FIRST_RU)]} {LAST_RU[i % len(LAST_RU)]}"


def date_for(i: int) -> str:
    month = 1 + (i % 12)
    day = 1 + (i % 28)
    return f"2024-{month:02d}-{day:02d}"


def case_prescription_inn(i: int) -> dict:
    patient = name_en(i)
    code, dname, _ = DIAGNOSES[i % len(DIAGNOSES)]
    med, dose = INN_MEDS[i % len(INN_MEDS)]
    d = date_for(i)
    text = (
        f"Document type: prescription\n"
        f"Patient: {patient}\n"
        f"Diagnosis: {code} {dname}\n"
        f"Medication: {med}\n"
        f"Dosage: {dose}\n"
        f"Date: {d}\n"
        f"Rp: {med}"
    )
    return {
        "id": f"rx_inn_{i:03d}",
        "text": text,
        "expected_type": "prescription",
        "expected": {
            "patient": {"full_name": patient},
            "diagnosis": {"code": code, "name": dname},
            "treatment": {"medication": med, "dosage": dose},
            "document_date": d,
        },
    }


def case_prescription_brand(i: int) -> dict:
    # чередуем EN/RU имена
    patient = name_ru(i) if i % 2 == 0 else name_en(i)
    code, dname_en, dname_ru = DIAGNOSES[i % len(DIAGNOSES)]
    dname = dname_ru if i % 2 == 0 else dname_en
    med, dose = BRAND_MEDS[i % len(BRAND_MEDS)]
    d = date_for(i)
    text = (
        f"Document type: prescription\n"
        f"Patient: {patient}\n"
        f"Diagnosis: {code} {dname}\n"
        f"Medication: {med}\n"
        f"Dosage: {dose}\n"
        f"Date: {d}\n"
        f"Rp: {med}"
    )
    return {
        "id": f"rx_brand_{i:03d}",
        "text": text,
        "expected_type": "prescription",
        "expected": {
            "patient": {"full_name": patient},
            "diagnosis": {"code": code, "name": dname},
            "treatment": {"medication": med, "dosage": dose},
            "document_date": d,
        },
    }


def case_discharge(i: int) -> dict:
    patient = name_en(i)
    code, dname, _ = DIAGNOSES[i % len(DIAGNOSES)]
    med, dose = INN_MEDS[i % len(INN_MEDS)]
    d = date_for(i)
    text = (
        f"Discharge Summary\n"
        f"Patient: {patient}\n"
        f"Diagnosis: {code} {dname}\n"
        f"Medication: {med}\n"
        f"Dosage: {dose}\n"
        f"Date: {d}"
    )
    return {
        "id": f"dc_{i:03d}",
        "text": text,
        "expected_type": "discharge",
        "expected": {
            "patient": {"full_name": patient},
            "diagnosis": {"code": code, "name": dname},
            "treatment": {"medication": med, "dosage": dose},
            "document_date": d,
        },
    }


def case_diagnosis(i: int) -> dict:
    use_ru = i % 3 == 0
    patient = name_ru(i) if use_ru else name_en(i)
    code, dname_en, dname_ru = DIAGNOSES[i % len(DIAGNOSES)]
    dname = dname_ru if use_ru else dname_en
    d = date_for(i)
    header = "Diagnosis Report" if not use_ru else "Заключение / диагноз"
    text = f"{header}\nPatient: {patient}\nDiagnosis: {code} {dname}\nDate: {d}"
    return {
        "id": f"dx_{i:03d}",
        "text": text,
        "expected_type": "diagnosis",
        "expected": {
            "patient": {"full_name": patient},
            "diagnosis": {"code": code, "name": dname},
            "treatment": None,
            "document_date": d,
        },
    }


def case_unknown(i: int) -> dict:
    text = UNKNOWN_TEXTS[i % len(UNKNOWN_TEXTS)]
    return {
        "id": f"unk_{i:03d}",
        "text": text,
        "expected_type": "unknown",
        "expected": {
            "patient": None,
            "diagnosis": None,
            "treatment": None,
            "document_date": None,
        },
    }


def build_cases(n: int = 200) -> list[dict]:
    """
    Распределение roughly:
    - 70 prescription INN
    - 50 prescription brand  ← важно для истории про аналоги
    - 40 discharge
    - 25 diagnosis
    - 15 unknown
    = 200
    """
    cases: list[dict] = []
    counts = {
        "rx_inn": 70,
        "rx_brand": 50,
        "dc": 40,
        "dx": 25,
        "unk": 15,
    }
    assert sum(counts.values()) == n

    for i in range(counts["rx_inn"]):
        cases.append(case_prescription_inn(i))
    for i in range(counts["rx_brand"]):
        cases.append(case_prescription_brand(i))
    for i in range(counts["dc"]):
        cases.append(case_discharge(i))
    for i in range(counts["dx"]):
        cases.append(case_diagnosis(i))
    for i in range(counts["unk"]):
        cases.append(case_unknown(i))

    return cases


def main() -> None:
    cases = build_cases(200)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=4), encoding="utf-8")
    print(f"Wrote {len(cases)} cases -> {OUT}")
    types: dict[str, int] = {}
    for c in cases:
        types[c["expected_type"]] = types.get(c["expected_type"], 0) + 1
    print("By type:", types)
    brands = sum(1 for c in cases if c["id"].startswith("rx_brand_"))
    print(f"Brand cases: {brands}")


if __name__ == "__main__":
    main()
