# Метрики RAG и QA

P007 · Qwen3-Embedding-8B, 4096d · GLM-5.3-Flash · top-8.
Измерения 5–6 сентября 2026 года; даты внутри корпуса синтетические.
Recall@8: средняя доля покрытых обязательных групп источников.
MRR: средний обратный ранг первого релевантного источника для вопросов с одной группой.
Отсутствующие факты без gold не входят в Recall/MRR. Это метрики поиска, не точность QA.

## Эксп. 1 — до

Корпус v1: 283 chunks, 60 вопросов. Recall: 48 вопросов; MRR: 37.

| Поиск | Recall@8 | MRR | p50 / p95, мс | Ошибки |
| --- | ---: | ---: | ---: | ---: |
| dense | 0.8333 | 0.7239 | 1835 / 7792 | 0/60 |
| dense + текстовый бонус внутри dense-пула | 0.8854 | 0.7820 | 230 / 341 | 0/60 |

[CSV](experiments/evaluations/p007-expanded-20260905/summary.csv) · [raw](experiments/evaluations/p007-expanded-20260905/raw.jsonl.gz) · [параметры](experiments/evaluations/p007-expanded-20260905/metadata.json)

## Эксп. 2 — BM25 + dense + RRF + LLM

Тот же корпус и вопросы. BM25 и dense ищут независимо; RRF(k=60).
Реранкер: до 60 кандидатов от каждого поиска → RRF top-16 → GLM → top-8.

| Поиск | Recall@8 | MRR | p50 / p95, мс | Ошибки |
| --- | ---: | ---: | ---: | ---: |
| bm25 | 0.7917 | 0.6676 | 18 / 27 | 0/60 |
| dense | 0.8333 | 0.7239 | 225 / 334 | 0/60 |
| hybrid | 0.8750 | 0.7257 | 211 / 297 | 0/60 |
| hybrid_rerank | **0.9479** | **0.9077** | 6299 / 9175 | 0/60 |

Выбран hybrid_rerank. 56 реранкингов, 4 пустые выдачи, 0 fallback.
Кэш и порядок влияют на время; реранкинг измерен в двух параллельных процессах.

[Поиск: CSV](experiments/evaluations/p007-hybrid-20260905/summary.csv) · [raw](experiments/evaluations/p007-hybrid-20260905/raw.jsonl.gz) · [параметры](experiments/evaluations/p007-hybrid-20260905/metadata.json)

[Реранкер: CSV](experiments/evaluations/p007-rerank-20260905/summary.csv) · [raw](experiments/evaluations/p007-rerank-20260905/raw.jsonl.gz) · [параметры](experiments/evaluations/p007-rerank-20260905/metadata.json)

## Эксп. 3 — корпус v2

36 файлов, 595 chunks, 180 вопросов. Recall core/dev/heldout: 48/52/54 вопросов; MRR heldout: 40.

| Поиск | Recall core | Recall dev | Recall heldout | MRR heldout | p50 / p95 heldout, мс |
| --- | ---: | ---: | ---: | ---: | ---: |
| bm25 | 0.7812 | 0.3750 | 0.8642 | 0.7321 | 36 / 54 |
| dense | 0.7708 | 0.6923 | 0.9105 | 0.8057 | 268 / 3625 |
| hybrid | 0.8438 | 0.5385 | 0.9167 | 0.8500 | 555 / 13328 |
| hybrid_rerank | 0.9271 | 0.7019 | **0.9722** | **0.9196** | 6547 / 13133 |

0 ошибок / 720 запросов; 174 реранкинга, 6 пустых выдач, 0 fallback. Три параллельных процесса.
Pipeline зафиксирован до измерения. Другой корпус: результаты не изолируют влияние алгоритма.

[Core CSV](experiments/evaluations/p007-corpus-v2-20260905/regression/summary.csv) · [dev CSV](experiments/evaluations/p007-corpus-v2-20260905/development/summary.csv) · [heldout CSV](experiments/evaluations/p007-corpus-v2-20260905/heldout/summary.csv) · [raw](experiments/evaluations/p007-corpus-v2-20260905/raw.jsonl.gz) · [параметры](experiments/evaluations/p007-corpus-v2-20260905/metadata.json)

## Эксп. 4 — корпус v3

150 документов / 162 файла, 216 сообщений, 80 комментариев, 769 chunks.
120 новых вопросов E181–E300; прежние 180 не переоценивались. Recall: 113 вопросов; MRR: 64.

| Поиск | Recall@8 | MRR | p50 / p95, мс | Ошибки | Fallback |
| --- | ---: | ---: | ---: | ---: | ---: |
| dense | 0.9142 | 0.8626 | 551 / 6753 | 0/120 | 0 |
| hybrid_rerank | **0.9646** | **0.9531** | 7068 / 17093 | 0/120 | 2 |

До трёх параллельных процессов. Два timeout → RRF включены в метрики; 4 выдачи с одним источником пропустили LLM.

[CSV](experiments/evaluations/p007-corpus-v3-20260905/summary.csv) · [raw](experiments/evaluations/p007-corpus-v3-20260905/raw.jsonl.gz) · [параметры](experiments/evaluations/p007-corpus-v3-20260905/metadata.json) · [индекс](experiments/corpus-v3/index-result.json) · [валидация](experiments/corpus-v3/validation.json)

## Эксп. 5 — проверка тезисов

Четыре контрастных кейса, 8 тезисов; один прогон каждого варианта. Это малый диагностический набор.

| Проверка | Верные оценки | Ложно принятые | Среднее время кейса, с |
| --- | ---: | ---: | ---: |
| Один общий LLM-вызов | 7/8 | 1/4 | 5.60 |
| Отдельные проверки + общий review | 8/8 | 0/4 | 9.99 |

[Датасет](../data/interview/verifier_cases.jsonl) · [общая: raw](experiments/qa-verification/batch-verifier-probe.json) · [отдельные: raw](experiments/qa-verification/isolated-verifier-probe.json)

## Эксп. 6 — переключатель проверки

Один вопрос в каждом режиме: «При каких условиях можно начать пилот?». Это два наблюдения, не средняя задержка.

| Режим | Результат | LLM-вызовы | Время, с |
| --- | --- | ---: | ---: |
| Без дополнительной проверки | not_checked | 4 | 32.94 |
| С проверкой | passed, 3/3 тезисов, один добор | 15 | 101.87 |

[Обычный: SSE](experiments/qa-verification/optional-verification-false-20260906T121037Z.json) · [С проверкой: SSE](experiments/qa-verification/optional-verification-true-20260906T121243Z.json)

`passed` — результат проверяющей LLM, не доказательство истинности. В UI проверка по умолчанию выключена; QA runner использует API-default `true`.

## Датасеты и воспроизведение

- [Все 300 вопросов](../data/interview/eval_cases.jsonl) · [core60](../data/interview/eval_core60.jsonl) · [dev60](../data/interview/eval_dev.jsonl) · [heldout60](../data/interview/eval_holdout.jsonl) · [splits + SHA-256](../data/interview/eval_splits.json)
- [data40](../data/interview/eval_collection_data.jsonl) · [operations40](../data/interview/eval_collection_operations.jsonl) · [quality40](../data/interview/eval_collection_quality.jsonl)
- [Корпус v1](experiments/backups/p007-before-corpus-v2-20260905.tar.gz) · [корпус v2](experiments/backups/p007-before-corpus-v3-20260905.tar.gz) · [корпус v3](../data/interview/README.md) · [manifest](../data/interview/manifest.json) · [CSV](../data/demo/)
- [Каталог фактов](../data/interview/collection/catalog.json) · [точные цитаты](../data/interview/collection/evidence_map.json) · [переписки](../data/interview/conversations.json) · [комментарии](../data/interview/task-comments.json)
- [SHA-256 артефактов](experiments/manifest.json). Крупные raw сжаты без изменения содержимого: `gzip -dc файл.jsonl.gz`.
- [Команды запуска оценки](../README.md#проверки-и-воспроизведение-оценки). Разметка синтетическая и предварительная; независимой человеческой оценки ещё нет.
