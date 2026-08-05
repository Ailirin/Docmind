# Eval

Gold-набор и скрипт для измерения качества **классификации** и **извлечения полей** (mock-экстрактор).

## Файлы

| Путь | Назначение |
|------|------------|
| `eval/gold/cases.jsonl` | JSON-массив кейсов (`id`, `text`, `expected_type`, `expected`) |
| `scripts/run_eval.py` | Прогон метрик |

## Запуск

Из корня репозитория (venv активен):

```powershell
python scripts/run_eval.py
```

## Что считается

1. **Classification accuracy** — `classify_document(text)` vs `expected_type`
2. **Field accuracy** — mock extract vs gold-поля:
   - `patient.full_name`
   - `diagnosis.code`
   - `treatment.medication`

Поля извлекаются с `DocumentType(expected_type)`, чтобы отдельно от классификации оценить regex-экстрактор.

Тексты кейсов в формате, который понимает mock: `Patient:`, `Diagnosis:`, `Medication:`, `Dosage:`, `Date:` (+ ключевые слова типа документа для классификатора).

## Последний прогон (mock)

- Classification accuracy: **17/17 = 1.000**
- Field accuracy (micro): **38/38 = 1.000**
  - patient.full_name: 14/14
  - diagnosis.code: 14/14
  - treatment.medication: 10/10
