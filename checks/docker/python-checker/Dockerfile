FROM python:3.11-slim

# Python не створює службові .pyc-файли всередині тимчасового
# середовища виконання користувацьких тестів.
ENV PYTHONDONTWRITEBYTECODE=1

# Вимкнення автоматичного завантаження сторонніх pytest-плагінів
# робить середовище тестування більш передбачуваним та ізольованим.
ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

# pytest використовується як інструмент автоматизованого запуску
# тестових сценаріїв у контейнері.
RUN pip install --no-cache-dir pytest

WORKDIR /workspace