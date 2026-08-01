# AI Workbench

Локальная offline-first среда для помощи в разработке: планирование задачи, подбор агентных ролей, работа с локальными LLM через Ollama, сохранение запусков и контроль действий.

Проект сделан как практический инструмент для фрилансеров и разработчиков, которым нужно быстрее разбирать задачи, получать план работ, проверять структуру проекта и вести разработку через последовательные шаги.

## Возможности

- локальный режим работы через Ollama;
- dashboard для проектов, запусков, агентов и настроек;
- создание задач на разработку или анализ проекта;
- агентные роли для frontend, backend, QA, документации, безопасности и архитектуры;
- сохранение запусков и шагов в SQLite;
- REST API для frontend-интерфейса;
- контроль потенциально опасных действий через approval-подход;
- базовая интеграция с инструментами чтения файлов, поиска по коду и подготовки патчей.

## Стек

- Backend: Python, FastAPI, SQLite.
- Frontend: React, TypeScript, Vite.
- AI/runtime: Ollama, локальные модели, provider routing.
- Проверки: pytest, Playwright smoke-сценарии.

## Структура

```text
ai-workbench/
├── backend/       # FastAPI backend, orchestrator, providers, storage
├── frontend/      # React/Vite dashboard
├── agents/        # описания агентных ролей
├── docs/          # архитектура, безопасность и использование
├── scripts/       # запуск и проверки
└── config.yaml    # локальная конфигурация
```

## Быстрый запуск

### 1. Проверить окружение

```bash
bash scripts/check_env.sh
```

### 2. Установить backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd ..
```

### 3. Установить frontend

```bash
cd frontend
npm install
cd ..
```

### 4. Запустить

```bash
bash scripts/dev.sh
```

После запуска dashboard доступен на `http://localhost:5173`.

## Документация

- [Architecture](./docs/architecture.md)
- [Usage](./docs/usage.md)
- [Safety](./docs/safety.md)
- [Agent platform roadmap](./docs/agent-platform-roadmap.md)

## Статус

Это личный pet-проект и рабочий эксперимент с локальными AI-инструментами. Он не заявляется как готовая коммерческая AI-платформа, но показывает подход к архитектуре, автоматизации разработки, agent workflow и offline-first работе с LLM.
