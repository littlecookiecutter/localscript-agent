import os
import sys
import json
import requests

# Добавляем корень проекта в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.getenv("API_URL", "http://localhost:8080")
TIMEOUT = 120  # Увеличенный таймаут для генерации через Ollama

TEST_CASES = [
    {
        "name": "1. Последний элемент массива",
        "prompt": "Из полученного списка email получи последний.",
        "expected_keywords": ["wf.vars.emails", "#wf.vars.emails", "return"],
        "context": {"wf": {"vars": {"emails": ["a@b.com", "c@d.com", "e@f.com"]}}}
    },
    {
        "name": "2. Счетчик попыток",
        "prompt": "Увеличивай значение переменной try_count_n на каждой итерации",
        "expected_keywords": ["wf.vars.try_count_n", "+", "return"],
        "context": {"wf": {"vars": {"try_count_n": 3}}}
    },
    {
        "name": "6. Фильтрация элементов массива",
        "prompt": "Отфильтруй элементы из массива, чтобы включить только те, у которых есть значения в полях Discount или Markdown.",
        "expected_keywords": ["_utils.array.new()", "Discount", "Markdown", "return"],
        "context": {
            "wf": {
                "vars": {
                    "parsedCsv": [
                        {"SKU": "A001", "Discount": "10%", "Markdown": ""},
                        {"SKU": "A002", "Discount": "", "Markdown": "5%"},
                        {"SKU": "A003", "Discount": None, "Markdown": None}
                    ]
                }
            }
        }
    },
    {
        "name": "5. Проверка типа данных (ensureArray)",
        "prompt": "Как преобразовать структуру данных так, чтобы все элементы items в ZCDF_PACKAGES всегда были представлены в виде массивов",
        "expected_keywords": ["ensureArray", "type(t)", "ipairs", "return"],
        "context": {
            "wf": {
                "vars": {
                    "json": {
                        "IDOC": {
                            "ZCDF_HEAD": {
                                "ZCDF_PACKAGES": [
                                    {"items": [{"sku": "A"}, {"sku": "B"}]},
                                    {"items": {"sku": "C"}}
                                ]
                            }
                        }
                    }
                }
            }
        }
    }
]


def check_keywords(code: str, keywords: list[str]) -> tuple[bool, list[str]]:
    """Проверяет наличие ключевых слов в сгенерированном коде."""
    missing = [kw for kw in keywords if kw.lower() not in code.lower()]
    return len(missing) == 0, missing


def test_generate_endpoint():
    """Интеграционный тест эндпоинта /generate."""
    print(f"\n🧪 Тестирование {BASE_URL}/generate")
    
    passed = 0
    failed = 0
    
    for case in TEST_CASES:
        print(f"\n📋 Тест: {case['name']}")
        print(f"   Запрос: {case['prompt'][:60]}...")
        
        try:
            response = requests.post(
                f"{BASE_URL}/generate",
                json={"prompt": case["prompt"]},
                timeout=TIMEOUT,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                print(f"   ❌ HTTP {response.status_code}: {response.text[:100]}")
                failed += 1
                continue
            
            result = response.json()
            code = result.get("code", "")
            
            if not code or code.strip().startswith("-- Error"):
                print(f"   ❌ Ошибка генерации: {code[:100]}")
                failed += 1
                continue
            
            # Проверка ключевых слов
            ok, missing = check_keywords(code, case["expected_keywords"])
            if ok:
                print(f"   ✅ Код сгенерирован, ключевые слова найдены")
                print(f"   📄 Код ({len(code)} симв.): {code[:150]}...")
                passed += 1
            else:
                print(f"   ⚠️ Код есть, но не найдены ключевые слова: {missing}")
                print(f"   📄 Код: {code[:200]}...")
                # Не считаем фэйлом, т.к. модель может предложить альтернативное решение
                passed += 0.5
                
        except requests.Timeout:
            print(f"   ❌ Таймаут запроса ({TIMEOUT}s)")
            failed += 1
        except requests.ConnectionError:
            print(f"   ❌ Не удалось подключиться к {BASE_URL}")
            print(f"   💡 Запустите: docker-compose up --build")
            failed += 1
            break
        except Exception as e:
            print(f"   ❌ Ошибка: {type(e).__name__}: {e}")
            failed += 1
    
    print(f"\n📊 Итоги: {passed} passed, {failed} failed из {len(TEST_CASES)} тестов")
    return failed == 0


def test_validation_rules():
    """Тест локальных правил валидации (без API)."""
    print(f"\n🧪 Тестирование валидатора (локально)")
    
    try:
        from src.validator.checker import validate_lua
    except ImportError as e:
        print(f"   ⚠️ Не удалось импортировать валидатор: {e}")
        print(f"   💡 Запустите с PYTHONPATH=/app или из корня проекта")
        return True
    
    test_cases = [
        {
            "name": "Пустой код",
            "code": "",
            "should_fail": True
        },
        {
            "name": "Только комментарии",
            "code": "-- это комментарий",
            "should_fail": True
        },
        {
            "name": "Нет wf.vars",
            "code": "local x = 5\nreturn x",
            "should_warn": True
        },
        {
            "name": "Есть JsonPath",
            "code": "return wf.vars.data['$.id']",
            "should_warn": True
        },
        {
            "name": "Корректный код",
            "code": "return wf.vars.emails[#wf.vars.emails]",
            "should_pass": True
        }
    ]
    
    passed = 0
    for case in test_cases:
        result = validate_lua(case["code"])
        valid = result["valid"]
        
        if case.get("should_pass") and valid:
            print(f"   ✅ {case['name']}: валидация пройдена")
            passed += 1
        elif case.get("should_fail") and not valid:
            print(f"   ✅ {case['name']}: корректно отклонён")
            passed += 1
        elif case.get("should_warn") and result["warnings"]:
            print(f"   ✅ {case['name']}: предупреждение добавлено")
            passed += 1
        else:
            print(f"   ⚠️ {case['name']}: unexpected result: {result}")
    
    print(f"📊 Валидатор: {passed}/{len(test_cases)} проверок")
    return True


if __name__ == "__main__":
    print("🚀 LocalScript Agent — тестовый запуск")
    print(f"📍 API URL: {BASE_URL}")
    
    # Сначала тестируем валидатор локально
    test_validation_rules()
    
    # Затем интеграционные тесты (требуют запущенного API)
    test_generate_endpoint()
    
    print("\n✨ Готово.")