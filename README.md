# Бот в коробке (-ах)

Это телеграм бот, который может поставляться в одном контейнере с UI администратора, postgres и minio для хранения данных

Версия 2.0 - теперь бот доступен и как отдельные контейнеры для развёртывания в k8s

## Keycloak (Внешняя зависимость)

Для запуска приложения потребуется иметь отдельно активированный и настроенный Keycloak для работы с UI администратора.

Требуется создать клиент с авторизацией.

Для локальной отладки можно воспользоваться реалмом, сохранёнными в директории `build/keycloak`. В нём следует создать собственного пользователя, дополнительные настройки для него не нужны.

Реалм автоматически подключается при запуске контейнеров.

## Сборка контейнеров

```bash
# Сборка общего контейнера
docker build . --push -f build/single-image/Dockerfile -t twobrowin/boxed-bots-si:2.x.x

# Сборка контейнера UI
docker build . --push -f build/separated-images/Dockerfile --build-arg APP_PATH=ui -t twobrowin/boxed-bots-ui:2.x.x

# Сборка контейнера бота
docker build . --push -f build/separated-images/Dockerfile --build-arg APP_PATH=bot -t twobrowin/boxed-bots-bot:2.x.x
```

## Локальная сборка и отладка

Для работы потребуется запущенные сервисы `postgres` (порт 5432) и `minio` (порт 9000) с настройками пользователей, указанными в файле `.env.example` (пароли можно изменить).

Следует скопировать `.env.example` в файл `.env` и заполнить недостающие поля или изменить под текущее окружение.

Для того чтобы запустить БД и Minio для отладки (не запускать бота в контейнере) следует указать параметр `START_SERVICES=false` и выполнить `docker-compose up` в директории `build/single-image`.

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
python -m src.ui.main
```

Запуск бота:

```bash
python -m src.bot.main
```

## Локальная отладка контейнера

Следует скопировать `.env.example` в файл `.env` и заполнить недостающие поля или изменить под текущее окружение.

```bash
# Запуск общего контейнера
cd build/single-image
docker compose up -d

# Запуск отдельных контейнеров
# Запуск выполняется отдельно из-за зависимости, которые не обрабатываются стандартными контейнерами
cd build/separated-images
docker compose up keycloak -d
docker compose up minio -d
docker compose up postgres -d
docker compose up ui -d
docker compose up bot -d
```

## Развёртывание | Ansible | Alumni

### Предвариательные требования

Установить коллекцию vats:

```bash
ansible-galaxy install -r deploy/alumni/requirements.yml
```

Установка docker:

```bash
ansible-playbook deploy/alumni/playbooks/_00_docker.yaml -i deploy/alumni/inventory.yaml
```

Получение сертификатов:

```bash
# Генерирование сертификатов
ansible-playbook deploy/alumni/playbooks/_01_certs.yaml -i deploy/alumni/inventory.yaml -t generate_certs

# Или

# Автоматическое получение сертификатов Let`s Encrypt
ansible-playbook deploy/alumni/playbooks/_01_certs.yaml -i deploy/alumni/inventory.yaml -t obtain_certs
```

### Доступ по ssh

```bash
ansible -i deploy/alumni/inventory.yaml all --module-name include_role --args name=bmstu.vats.ssh_connection
```

### Запуск бота

```bash
ansible-playbook deploy/alumni/playbooks/_02_deploy.yaml -i deploy/alumni/inventory.yaml
```

## [Удалено] Развёртывание | K8s | Mic-call

Следует создать и подготовить:
* Неймспейс bmstu
* Доступ в Keycloak, приложение mic-call с ролью ui-user
* Доступ в Minio, ключ доступа mic-call
* Доступ в Postgres, пользователь и БД от его имени mic-call
* Заполнить секреты и переменные окружения

```bash
helm upgrade --install --debug mic-call ./deploy/charts/ -n bmstu -f ./deploy/charts/values_mic-call.yaml
```

## [Удалено] Развёртывание | K8s | Baumanec-call-2025

Следует создать и подготовить:
* Неймспейс baumanec
* Доступ в Keycloak, приложение baumanec-call-2025 с ролью ui-user
* Доступ в Minio, ключ доступа baumanec-call-2025
* Доступ в Postgres, пользователь и БД от его имени baumanec-call-2025
* Заполнить секреты и переменные окружения

```bash
helm upgrade --install --debug baumanec-call-2025 ./deploy/charts/ -n baumanec -f ./deploy/charts/values_baumanec-call-2025.yaml
```

## Развёртывание | K8s | Dev-ops-it-2025

Следует создать и подготовить:
* Неймспейс bmstu
* Доступ в Keycloak, приложение dev-ops-it-2025 с ролью ui-user
* Доступ в Minio, ключ доступа dev-ops-it-2025
* Доступ в Postgres, пользователь и БД от его имени dev-ops-it-2025
* Заполнить секреты и переменные окружения

```bash
helm upgrade --install --debug dev-ops-it-2025 ./deploy/charts/ -n bmstu -f ./deploy/charts/values_dev-ops-it-2025.yaml
```