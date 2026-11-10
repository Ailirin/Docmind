"""Мелкие утилиты безопасности, общие для API-ключа, админки и /metrics."""

import secrets


def constant_time_equals(provided: str, expected: str) -> bool:
    """
    Сравнение секретов за постоянное время (защита от timing-атак).

    Fail closed: если ожидаемый секрет пуст (например, переменная окружения не
    задана и docker-compose подставил пустую строку), аутентифицировать НЕКОГО.
    Без этого compare_digest("", "") == True, и пустой заголовок/пароль проходил бы.
    """
    if not expected:
        return False
    return secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))
