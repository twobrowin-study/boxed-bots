# Бот клуба выпускников МГТУ

Это телеграм бот, который поставляется в одном контейнере с UI администратора, postgres и minio для хранения данных

## Keycloak (Внешняя зависимость)

Для запуска приложения потребуется иметь отдельно активированный и настроенный Keycloak для работы с UI администратора.

Требуется создать клиент с авторизацией.

Для локальной отладки можно воспользоваться реалмом, сохранёнными в директории `keycloak`. В нём следует создать собственного пользователя, дополнительные настройки для него не нужны.

Реалм автоматически подключается при запуске контейнеров.

## Сборка контейнера

```bash
docker compose build --push
```

## Локальная сборка и отладка

Для работы потребуется запущенные сервисы `postgres` (порт 5432) и `minio` (порт 9000) с настройками пользователей, указанными в файле `.env.example` (пароли можно изменить).

Следует скопировать `.env.example` в файл `.env` и заполнить недостающие поля или изменить под текущее окружение.

Для того чтобы запустить БД и Minio для отладки (не запускать бота в контейнере) следует указать параметр `START_SERVICES=false` и выполнить `docker-compose up`.

Установка окружения:

```bash
poetry install
```

Запуск окружения:

```bash
poetry shell
```

Запуск UI администратора:

```bash
python src/ui/main.py
```

Запуск бота:

```bash
python src/bot/main.py
```

## Локальная отладка контейнера

Следует скопировать `.env.example` в файл `.env` и заполнить недостающие поля или изменить под текущее окружение.

```bash
docker-compose up
```

## Развёртывание

### Предвариательные требования

Установить коллекцию vats:

```bash
ansible-galaxy install -r deploy/requirements.yml
```

Установка docker:

```bash
ansible-playbook deploy/playbooks/_00_docker.yaml -i deploy/inventory.yaml
```

Получение сертификатов:

```bash
# Генерирование сертификатов
ansible-playbook deploy/playbooks/_01_certs.yaml -i deploy/inventory.yaml -t generate_certs

# Или

# Автоматическое получение сертификатов Let`s Encrypt
ansible-playbook deploy/playbooks/_01_certs.yaml -i deploy/inventory.yaml -t obtain_certs
```

### Доступ по ssh

```bash
ansible -i deploy/inventory.yaml all --module-name include_role --args name=bmstu.vats.ssh_connection
```

### Запуск бота

```bash
ansible-playbook deploy/playbooks/_02_deploy.yaml -i deploy/inventory.yaml
```
