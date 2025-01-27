## Twitter clone
Этот проект представляет собой клона социальной сети Twitter. Возможности:

1. Пользователь может добавить новый твит.
2. Пользователь может удалить свой твит.
3. Пользователь может зафоловить другого пользователя.
4. Пользователь может отписаться от другого пользователя.
5. Пользователь может отмечать твит как понравившийся.
6. Пользователь может убрать отметку «Нравится».
7. Пользователь может получить ленту из твитов отсортированных в
порядке убывания по популярности от пользователей, которых он
фоловит.
8. Твит может содержать картинку.

### Установка и запуск

Убедитесь, что у вас установлены Docker, docker-compose и PostgreSQL.

Клонируйте репозиторий:

```
git clone https://gitlab.skillbox.ru/nadezhda_barinova/python_advanced_diploma.git
```
Затем перейдите в папку репозитория:
```
cd python_advanced_diploma
```
Для запуска приложения нужно ввести эту команду:
```
docker compose up -d
```
Для остановки работы приложения нужно ввести следующую команду:
```
docker compose stop
```
Для удаления используйте эту команду:
```
docker compose rm
```
### Запуск тестов
Для запуска тестов введите следующие команды:
```
cd test_app
docker compose up -d
```
Не забудьте перед этим предоставить доступ к появившейся папке с базой данных test_db.
После этого произведите запуск тестов из корневой папки проекта:
```
pytest
```
Для остановки работы тестов нужно ввести следующую команду:
```
docker compose stop
```
Для очистки используйте эту команду:
```
docker compose rm
```
### Документация
Для открытия документации вам нужно запустить приложение и перейти по этой ссылке: http://0.0.0.0:8080/api/docs