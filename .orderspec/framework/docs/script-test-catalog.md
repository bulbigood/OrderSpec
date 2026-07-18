# Каталог скриптов и тестов

Этот файл — карта Python-кода OrderSpec для разработчиков и ИИ-агентов. Перед чтением исходников найдите здесь нужную область. Пути в таблицах указаны относительно `.orderspec/framework/`.

## Правила

- Исполняемые модули и библиотеки: `scripts/<subject>.py`, только `snake_case`.
- Тесты: целевой стандарт `scripts/test/test_<subject>.py`, только `snake_case` после префикса `test_`.
- Каждый Python-файл начинается с краткого module docstring, после необязательного shebang. Docstring объясняет ответственность модуля, а не историю изменений.
- CLI-файл оставляет в одном месте только разбор аргументов и композицию; доменная логика, ввод-вывод и валидация живут в отдельных модулях.
- Один тестовый файл проверяет один production-модуль или один явно названный сквозной контракт.

Текущий runner принимает только канонический шаблон `test_*.py`. Это предотвращает повторное появление смешанных стилей именования.

## Крупнейшие файлы и план декомпозиции

Размеры зафиксированы на 2026-07-19. Приоритет — файлы от 500 строк; граница не является автоматическим требованием к разбиению.

### Скрипты

| Файл | Строк | Предлагаемые кластеры |
|---|---:|---|
| `scripts/bootstrap_contracts.py` | 1391 | `bootstrap/evidence.py` (fingerprints/inventory), `bootstrap/stack_detection.py` (Node/Python/Go/Rust/Java), `bootstrap/render.py`, `bootstrap/validation.py`, `bootstrap/commands.py`; исходный файл оставить CLI-фасадом. |
| `scripts/trace_validate.py` | 1089 | `trace_validation/spec_checks.py`, `plan_checks.py`, `task_checks.py`, `contract_risks.py`, `matrices.py`; общий тип finding и collector вынести в `trace_validation/model.py`. |
| `scripts/command_context.py` | 1071 | `command_context/schema.py` (shape validation), `expansion.py` (manifest/glob/resource expansion), `feature.py`, `resolver.py`; CLI — отдельно. |
| `scripts/trace_commands.py` | 926 | Команды сгруппировать в `trace_ops/state.py`, `extract.py`, `mechanisms.py`, `diff.py`; разрешение feature/path вынести в общий `trace_ops/paths.py`. |
| `scripts/code_workflow.py` | 897 | `code_pipeline/protocol.py`, `preflight.py`, `packets.py`, `attempts.py`, `repository_snapshot.py`; CLI-фасад сохраняет текущий JSON-контракт. |
| `scripts/active_feature.py` | 871 | `active_feature/state.py`, `discovery.py`, `validation.py`, `commands.py`; атомарный JSON I/O переиспользовать из общего persistence-модуля. |
| `scripts/setup.py` | 788 | По одному обработчику в `setup_commands/{spec,plan,tasks,code,checks}.py`, общие path payload и output helpers — в `setup_commands/common.py`. |
| `scripts/agents_sync.py` | 609 | `agents/state.py`, `detection.py`, `synchronization.py`, `rules.py`, `workers.py`; adapter API оставить в `adapters/`. |
| `scripts/frontmatter.py` | 538 | Парсер/нормализация в `frontmatter/parser.py`, валидаторы типов артефактов в `frontmatter/validators.py`, dispatch/CLI отдельно. |

Дополнительно `adapters/codex.py` (731 строка) стоит разделить на detection, TOML/config I/O, prompt/skill sync и worker lifecycle. `scripts/automation_policy.py` (488 строк) близок к границе: schema validation отделить от matching/classification.

При разбиении сначала добавить characterization-тесты публичного CLI: exit code, JSON stdout, stderr и файловые эффекты. Затем переносить чистые функции кластер за кластером без изменения командного контракта.

### Тесты

| Файл | Строк | Предлагаемые кластеры |
|---|---:|---|
| `scripts/test/test_traceability.py` | 1070 | По CLI-командам: init/get/put, validate, plan/mechanisms, consumed-state; feature fixture вынести отдельно. |
| `scripts/test/test_agents_sync.py` | 1049 | detection, synchronization, rules, worker configuration и по одному adapter contract suite; mock workspace — общий fixture. |
| `scripts/test/test_validate.py` | 973 | Разделить проверки по семействам M-rules и стадиям spec/plan/tasks; не смешивать lint/extract сценарии. |
| `scripts/test/test_active_feature.py` | 878 | state CRUD, discovery/resolution, lifecycle status, invalid/corrupt state и CLI contract. |
| `scripts/test/test_validate_status_codes.py` | 728 | Чистые extractor unit-тесты, M19, M29 и отдельные end-to-end validate cases. |
| `scripts/test/test_bootstrap_contracts.py` | 643 | Stack detector suites по экосистемам, rendering, audit/migration, init/complete CLI; workspace builders — в support. |
| `scripts/test/test_setup.py` | 518 | Path resolution и отдельные command suites для plan/tasks/code/checks. |

Избегать одного глобального mutable workspace на весь файл: каждый кластер должен владеть временным каталогом. Повторяющиеся `ok`/`bad`, `run_*`, `write` и `reset_*` собрать в маленькие support-модули, но assertions оставить рядом со сценарием.

Декомпозиция бывшего монолитного command-context теста завершена 2026-07-19: core resolution, validation/output, real-manifest и resource/group сценарии запускаются независимо, общий subprocess/workspace harness вынесен в `test/support/command_context.py`.

Декомпозиция бывшего монолитного frontmatter теста завершена 2026-07-19: command prompts, gate reports, contracts/protocols, feature spec и CLI edge cases запускаются независимо, общий harness вынесен в `test/support/frontmatter.py`.

## Скрипты

### Workflow, feature и task lifecycle

| Файл | Назначение |
|---|---|
| `scripts/active_feature.py` | Выбирает active feature, нормализует и валидирует её lifecycle state, ищет feature по ID/пути. |
| `scripts/bootstrap_contracts.py` | Обнаруживает стек и структуру проекта, создаёт, мигрирует, проверяет и аудитит project contracts. |
| `scripts/bootstrap_workflow.py` | Детерминированно выбирает фазу unified `/order.bootstrap`. |
| `scripts/code_obligations.py` | Строит и обновляет ledger обязательств для `/order.code-check`. |
| `scripts/code_workflow.py` | Управляет preflight, worker packets, попытками и завершением `/order.code`. |
| `scripts/default_mode.py` | Выбирает безопасный режим команды без аргументов по текущему состоянию pipeline. |
| `scripts/feature_spec.py` | Выделяет канонический каталог новой feature без записи содержимого spec. |
| `scripts/task_context.py` | Разбирает task-context и выдаёт разрешённый worker file context. |
| `scripts/task_contract_context.py` | Собирает для задачи минимальные выдержки project/spec contracts. |
| `scripts/task_progress.py` | Сверяет результаты worker и атомарно переводит task checkboxes в завершённое состояние. |
| `scripts/task_refine.py` | Защищает завершённые задачи при transactional refinement `tasks.md`. |
| `scripts/work_order.py` | Фиксирует baseline work order и безопасно откатывает только разрешённые пути. |
| `scripts/workflow_feedback.py` | Хранит typed handoff о дефектах между стадиями и отмечает их потребление. |
| `scripts/workflow_supervisor.py` | Хранит состояние continuous run, классифицирует события и поддерживает pause/resume. |

### Command context, setup и gates

| Файл | Назначение |
|---|---|
| `scripts/command_context.py` | Валидирует manifest и материализует required/read-if-exists context для команды. |
| `scripts/command_input.py` | Отделяет управляющие флаги OrderSpec от семантического текста пользователя. |
| `scripts/gate_target.py` | Read-only разрешает target gate и аргументы команды. |
| `scripts/setup.py` | Вычисляет пути и prerequisites для spec/plan/tasks/code и их check-команд. |
| `scripts/upstream_gate.py` | Проверяет наличие upstream artifact и допустимость verdict/consumed-stale report. |
| `scripts/validate_code_report.py` | Проверяет и финализирует code-check report и стабильные finding IDs. |
| `scripts/validate_gate_report.py` | Сверяет generic gate report с результатом механической проверки. |

### Traceability и artifact validation

| Файл | Назначение |
|---|---|
| `scripts/frontmatter.py` | Парсит и валидирует YAML frontmatter всех типов артефактов OrderSpec. |
| `scripts/traceability.py` | CLI-фасад для traceability state, extraction, validation, diff и mechanisms. |
| `scripts/trace_commands.py` | Реализует команды traceability CLI и операции с feature state. |
| `scripts/trace_constants.py` | Хранит маркеры, колонки, regex и ID-константы traceability. |
| `scripts/trace_lint.py` | Проверяет строки mechanisms, trace и spec-ids TSV. |
| `scripts/trace_mechanisms.py` | Проверяет терминальные mechanisms и coverage связей. |
| `scripts/trace_parse.py` | Извлекает IDs, таблицы, pathmanifest и связи из Markdown. |
| `scripts/trace_tsv.py` | Читает, проверяет и атомарно пишет traceability TSV. |
| `scripts/trace_validate.py` | Выполняет межартефактные M-checks и строит validation matrices/categories. |

### Automation, agents и общая инфраструктура

| Файл | Назначение |
|---|---|
| `scripts/agents_sync.py` | Обнаруживает AI-агентов, синхронизирует prompts/skills/rules и настраивает workers. |
| `scripts/automation_policy.py` | Валидирует automation config/events и классифицирует AUTO_ROUTE/RETRY/PAUSE/STOP. |
| `scripts/common.py` | Общие path, process, JSON и feature-state helpers для скриптов. |
| `scripts/run_all_tests.py` | Находит и последовательно запускает весь script test suite с timeout и summary. |
| `scripts/tooling_config.py` | Читает, обновляет и мигрирует `tooling.json` v2 → v3. |
| `scripts/validate_tooling.py` | Проверяет tooling v3 против project contracts и установленных skills. |

## Адаптеры

| Файл | Назначение |
|---|---|
| `adapters/__init__.py` | Обозначает пакет integrations. |
| `adapters/base.py` | Определяет `AgentInfo` и абстрактный adapter contract. |
| `adapters/claude_code.py` | Интеграция Claude Code: detection, prompts, skills и workers. |
| `adapters/codex.py` | Интеграция Codex: config, prompts, skills и workers. |
| `adapters/jsonc_utils.py` | Читает и пишет JSONC для конфигурации Kilo Code. |
| `adapters/kilocode.py` | Интеграция Kilo Code, включая legacy layout. |
| `adapters/registry.py` | Перечисляет адаптеры и ищет их по agent ID. |

## Тесты

### Workflow, feature и tasks

| Файл | Что проверяет |
|---|---|
| `scripts/test/test_active_feature.py` | CRUD, discovery, selection и validation active-feature state. |
| `scripts/test/test_bootstrap_contracts.py` | Stack inference, создание, migration, audit и validation contracts. |
| `scripts/test/test_bootstrap_workflow.py` | Маршрутизацию фаз unified bootstrap. |
| `scripts/test/test_code_obligations.py` | Построение и обновление code-check obligation ledger. |
| `scripts/test/test_code_workflow.py` | Preflight, packets, attempt lifecycle и terminal checks code workflow. |
| `scripts/test/test_default_mode.py` | Выбор режима команд без аргументов. |
| `scripts/test/test_feature_spec.py` | Выделение feature ID и каталога. |
| `scripts/test/test_feedback_recovery_flow.py` | Сквозное восстановление code → spec refine → tasks refine → resume. |
| `scripts/test/test_task_context.py` | Парсинг task context, path policy и worker whitelist. |
| `scripts/test/test_task_contract_context.py` | Выбор минимального contract context для задачи. |
| `scripts/test/test_task_progress.py` | Reconciliation, completion и validation worker result. |
| `scripts/test/test_task_refine.py` | Сохранность завершённых задач при refinement. |
| `scripts/test/test_work_order.py` | Capture и ограниченный rollback work order. |
| `scripts/test/test_workflow_feedback.py` | Создание, listing и consumption cross-stage feedback. |
| `scripts/test/test_workflow_supervisor.py` | Start/evaluate/answer/status/resume supervisor state machine. |

### Command setup, gates и prompt contracts

| Файл | Что проверяет |
|---|---|
| `scripts/test/test_blocking_feedback_contract.py` | Статический контракт blocking-feedback routing/intake. |
| `scripts/test/test_command_context_core.py` | Загрузку manifest и базовое разрешение command context. |
| `scripts/test/test_command_context_validation.py` | Manifest validation и стабильность выходного JSON-контракта. |
| `scripts/test/test_command_context_manifest.py` | Разрешение контекста по реальному framework manifest. |
| `scripts/test/test_command_context_resources.py` | Resource references, groups, порядок expansion и циклы. |
| `scripts/test/test_command_input.py` | Разделение controls и semantic input. |
| `scripts/test/test_gate_purity.py` | Отсутствие мутаций у inspector-only gate surfaces. |
| `scripts/test/test_gate_target.py` | Read-only разрешение target и command args. |
| `scripts/test/test_order_bootstrap_tooling.py` | Политику discovery/install skills в bootstrap prompt. |
| `scripts/test/test_order_code_contract.py` | Статическую wiring-схему `/order.code`. |
| `scripts/test/test_order_plan_prompt.py` | Структуру и правила plan/plan-check prompts и template. |
| `scripts/test/test_order_plan_tooling.py` | Tooling delegation в plan prompt. |
| `scripts/test/test_order_tasks_check_prompt.py` | Контракт tasks-check prompt. |
| `scripts/test/test_self_gate_mode_order.py` | Приоритет Refine перед Refresh при blocking self-gate. |
| `scripts/test/test_setup_code_check.py` | Setup payload и prerequisites для code-check. |
| `scripts/test/test_setup_shell_vars.py` | Форматы `--shell-vars` и `--json`. |
| `scripts/test/test_setup.py` | Path resolution и основные setup subcommands. |
| `scripts/test/test_setup_spec_check.py` | Setup для spec-check. |
| `scripts/test/test_setup_tasks_check.py` | Setup для tasks-check. |
| `scripts/test/test_upstream_gate.py` | Artifact/report lifecycle и exit codes upstream gate. |
| `scripts/test/test_validate_code_report.py` | Parsing, validation, finalization и finding IDs code report. |
| `scripts/test/test_validate_gate_report.py` | Финализацию generic gate report по mechanical result. |

### Traceability, parsing и validation

| Файл | Что проверяет |
|---|---|
| `scripts/test/test_diff.py` | Traceability diff summary. |
| `scripts/test/test_extract_spec_ids.py` | Извлечение spec IDs. |
| `scripts/test/test_extract_trace.py` | Извлечение trace rows. |
| `scripts/test/test_extract.py` | Совместный extract-spec/extract-trace/lint regression flow. |
| `scripts/test/test_frontmatter_prompts.py` | Frontmatter command prompts. |
| `scripts/test/test_frontmatter_reports.py` | Frontmatter gate reports. |
| `scripts/test/test_frontmatter_contracts.py` | Frontmatter project contracts, framework rules и protocols. |
| `scripts/test/test_frontmatter_spec.py` | Frontmatter feature spec и вложенные refs/generator fields. |
| `scripts/test/test_frontmatter_cli.py` | Exit codes и текстовый режим frontmatter CLI. |
| `scripts/test/test_get.py` | Чтение traceability state командой get. |
| `scripts/test/test_lint.py` | Lint mechanisms/trace/spec-ids. |
| `scripts/test/test_nfr_provenance.py` | MUST-level NFR provenance. |
| `scripts/test/test_put.py` | Transactional запись traceability tables. |
| `scripts/test/test_test_topology.py` | Проверку test topology в mechanisms. |
| `scripts/test/test_trace_matrices.py` | Качество IF/AC/category matrices. |
| `scripts/test/test_trace_validate_categories.py` | Определение semantic categories и journey matrix. |
| `scripts/test/test_trace_validate_glossary.py` | Определение glossary независимо от номера раздела. |
| `scripts/test/test_traceability_get_feature_dir.py` | `get` с явным `--feature-dir` без positional feature. |
| `scripts/test/test_traceability_mark_consumed.py` | Запись marker `CONSUMED_STALE`. |
| `scripts/test/test_traceability.py` | Основной traceability CLI и cross-artifact validation. |
| `scripts/test/test_validate_grid_rows.py` | Парсинг grid rows и защиту от ложного header match. |
| `scripts/test/test_validate_status_codes.py` | Status-code extraction и M19/M29 coverage checks. |
| `scripts/test/test_validate.py` | Полный набор traceability validation rules. |

### Agents, automation и tooling

| Файл | Что проверяет |
|---|---|
| `scripts/test/test_agents_sync.py` | Detection/sync/rules/workers для всех agent adapters. |
| `scripts/test/test_automation_policy.py` | Event/config validation, classification и safety overrides. |
| `scripts/test/test_validate_tooling.py` | Tooling v3 bindings и generic contract references. |

## Состояние именования и документации

- Все 36 файлов непосредственно в `scripts/` соответствуют `snake_case.py`.
- Все 63 запускаемых теста соответствуют формату `test_<subject>.py` и используют только `snake_case`.
- Runner обнаруживает только канонический формат, поэтому новое несовместимое имя не будет незаметно принято suite.
- На дату аудита все 36 script-модулей, 63 теста, 3 test-support модуля и 7 adapter-модулей имеют module docstring в начале файла.

Миграция исторических kebab-case имён завершена 2026-07-19. При добавлении теста используйте имя production-модуля после `test_`, например `active_feature.py` → `test_active_feature.py`.

## Test support

| Файл | Назначение |
|---|---|
| `scripts/test/support/__init__.py` | Обозначает пакет переиспользуемой тестовой инфраструктуры. |
| `scripts/test/support/command_context.py` | Даёт command-context тестам изолированный workspace, builders, subprocess helpers и summary/cleanup. |
| `scripts/test/support/frontmatter.py` | Даёт frontmatter тестам изолированный workspace, CLI helpers и summary/cleanup. |
