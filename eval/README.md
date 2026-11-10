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

## Последний прогон (mock, 200 кейсов)

- Classification accuracy: **200/200 = 1.000**
- Field accuracy (micro): **530/530 = 1.000**
  - patient.full_name: 185/185
  - diagnosis.code: 185/185
  - treatment.medication: 160/160

Сохранённые прогоны (`--out`) лежат в `eval/results/`:

| Файл | Провайдер | Поля (micro) |
|------|-----------|-------------:|
| `mock_200.json` | mock | 530/530 = 1.000 |
| `llm_good_v2.json` | llm, промпт v2 | 114/530 = 0.215 |
| `llm_good_v3.json` | llm, промпт v3 | 529/530 = 0.998 |
| `llm_bad_prompt.json`, `llm_good_prompt.json` | llm, ранние итерации (22 кейса) | 14/53 = 0.264, 25/53 = 0.472 |

Кейсы синтетические (шаблонные), поэтому метрики — регрессионный тест, а не оценка на реальных документах.
