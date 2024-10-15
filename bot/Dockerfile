# Используем оф.образ Python 3.12
FROM python:3.12-slim
# Используем директорию с bot.py
WORKDIR .
# Копируем файлы в образ
COPY . .
# Обновляем репозитории и устанавливаем необходимые для библиотек
# Python зависимости
RUN apt-get update && apt-get install libpq-dev gcc -y
# Устанавливаем необходимые для работы бота библиотеки
RUN pip install -r requirements.txt
# Запускаем bot.py
CMD ["python", "bot.py"]
