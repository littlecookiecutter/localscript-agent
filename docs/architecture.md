Вот код для 4 файлов. Каждый в отдельном блоке — копируй и сохраняй.

---

### 📄 `docs/architecture.md`
```markdown
# Архитектура LocalScript Agent (C4 Model)

## System Context
```mermaid
C4Context
  title System Context: LocalScript Agent

  Person(user, "Пользователь", "Формулирует задачу на естественном языке")
  
  System_Boundary(system, "LocalScript Agent") {
    Container(api, "API Gateway", "FastAPI, порт 8080", "Принимает запросы /generate")
    Container(agent, "Agent Core", "Python", "Генерация + валидация + цикл исправлений")
    ContainerDb(ollama, "Ollama", "Local LLM", "Qwen2.5-Coder-7B-Instruct, 8GB VRAM")
  }

  Rel(user, api, "POST /generate {prompt}", "HTTPS")
  Rel(api, agent, "Вызов агента", "sync")
  Rel(agent, ollama, "Генерация кода", "localhost:11434")
  Rel(agent, agent, "Цикл валидации", "внутренний")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Container: Agent Core
```mermaid
C4Container
  title Container: Agent Core

  Container_Boundary(agent, "Agent Core") {
    Component(prompt_builder, "PromptBuilder", "Python", "Формирует системный промпт с правилами LowCode")
    Component(code_extractor, "CodeExtractor", "Python", "Извлекает lua{...}lua или ```lua из ответа LLM")
    Component(validation_loop, "ValidationLoop", "Python", "Запускает цикл: генерация → валидация → исправление")
    Component(ollama_client, "OllamaClient", "Python", "HTTP-клиент к localhost:11434")
  }

  ContainerDb(validator, "Lua Checker", "luac/subprocess", "Синтаксическая проверка + LowCode-правила")

  Rel(prompt_builder, ollama_client, "Передаёт промпт")
  Rel(ollama_client, code_extractor, "Получает ответ")
  Rel(code_extractor, validation_loop, "Передаёт извлечённый код")
  Rel(validation_loop, validator, "Запускает валидацию")
  Rel(validation_loop, prompt_builder, "При ошибке: новый промпт с логом")
```

## Ключевые потоки данных

### 1. Генерация кода
```
Пользователь → POST /generate {"prompt": "..."}
                ↓
API → LuaAgent.generate(prompt)
                ↓
PromptBuilder + системные правила → Ollama API
                ↓
Ответ модели → CodeExtractor → lua{код}lua
                ↓
ValidationLoop → validate_lua() → {valid, errors, warnings}
                ↓
Если valid → вернуть {"code": "..."}
Если !valid и итераций < 2 → повтор с "Исправь: {errors}"
```

### 2. Валидация (оффлайн)
```
validate_lua(code):
  1. subprocess ["luac", "-p", "-"] → синтаксис
  2. Проверка: код не пустой?
  3. Проверка: есть wf.vars / wf.initVariables?
  4. Проверка: нет "$.", "JsonPath", "wf.data."?
  5. Проверка: есть return в конце?
  → вернуть {valid: bool, errors: [], warnings: []}
```

## Локальность и безопасность
- ✅ Все компоненты работают внутри Docker-контура
- ✅ Нет исходящих соединений к внешним AI-API
- ✅ Модель загружается локально через `ollama pull`
- ✅ Данные пользователя не покидают хост
- ✅ Воспроизводимость: одна команда `docker-compose up --build`

## Требования к ресурсам
| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| GPU VRAM | 8 GB | 12 GB |
| RAM | 16 GB | 32 GB |
| CPU | 4 ядра | 8 ядер |
| Диск | 20 GB (для модели) | 50 GB |

## Параметры запуска модели
```bash
ollama run qwen2.5-coder:7b-instruct-q4_k_m \
  --num_ctx 4096 \
  --num_predict 256 \
  --batch 1 \
  --parallel 1
```
</think>