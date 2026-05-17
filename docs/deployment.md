# Развёртывание Whois Watcher

Пошаговая инструкция по поднятию проекта на чистом production-сервере.
Основана на реальном опыте развёртывания.

В этом документе — конкретные команды и подводные камни, на которые я
наткнулся в живом деплое. Архитектурные обоснования — в
[architecture.md](architecture.md) и [decisions.md](decisions.md), сюда
не дублирую.

---

## Системные требования

| Параметр | Минимум | Комментарий |
|----------|---------|-------------|
| ОС | Ubuntu 24.04 LTS, 64-bit | Проверялось на этом дистрибутиве; другие современные Linux должны работать. |
| CPU | 2 vCPU | Хватает для ~1000 пользователей и нескольких десятков тысяч доменов. |
| RAM | 4 GB | Postgres + Redis + 3 Python-процесса. |
| Диск | 40 GB SSD | Образы Docker + Postgres-данные + логи. |
| Docker | 24+ | C Docker Compose v2 (плагин `docker compose`, не `docker-compose`). |
| Сеть — исходящие | TCP/43 (WHOIS), TCP/443 (RDAP), TCP/53 (DNS) | По умолчанию весь WHOIS-трафик идёт через локальный proxy на 127.0.0.1:8043 (ADR 028). Если хостер закрывает TCP/43 и прокси упал — fallback на `lookup_direct` потеряет часть зон. |
| Сеть — входящие | TCP/22 (SSH), TCP/80 (ACME), TCP/8443 (Telegram webhook), опц. TCP/443 | Telegram webhook принимает только порты 80, 88, 443, 8443. См. [почему 8443](#почему-8443-а-не-443). |
| Домен | Любой, с возможностью настроить A-запись | Нужен для HTTPS-webhook. Let's Encrypt бесплатно даёт сертификат. |

---

## Подготовка сервера

### 1. Базовые пакеты

```bash
sudo apt update
sudo apt install -y \
    dnsutils \
    netcat-openbsd \
    ufw \
    fail2ban \
    curl \
    wget \
    git \
    tmux \
    ca-certificates
```

### 2. Пользователь для проекта

Не запускайте сервисы от `root`. Создайте отдельного пользователя:

```bash
sudo useradd -m -s /bin/bash -G sudo whoiswatcher
sudo passwd whoiswatcher          # задайте надёжный пароль
sudo mkdir -p /home/whoiswatcher/.ssh
sudo cp ~/.ssh/authorized_keys /home/whoiswatcher/.ssh/
sudo chown -R whoiswatcher:whoiswatcher /home/whoiswatcher/.ssh
sudo chmod 700 /home/whoiswatcher/.ssh
sudo chmod 600 /home/whoiswatcher/.ssh/authorized_keys
```

Опционально — passwordless sudo (удобнее для CI-сценариев, но безопаснее
оставить пароль и логиниться по SSH-ключу):

```bash
echo 'whoiswatcher ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/whoiswatcher
sudo chmod 440 /etc/sudoers.d/whoiswatcher
```

Дальше все команды — от `whoiswatcher`, кроме явных `sudo`.

### 3. Файрвол (ufw)

> **ВАЖНО:** сначала разрешите SSH, потом включайте ufw. Иначе залочите сами себя.

```bash
sudo ufw allow 22/tcp   comment 'SSH'
sudo ufw allow 80/tcp   comment 'HTTP / Let'\''s Encrypt'
sudo ufw allow 443/tcp  comment 'HTTPS (optional)'
sudo ufw allow 8443/tcp comment 'Telegram webhook'
sudo ufw enable          # подтвердите y
sudo ufw status verbose
```

### 4. fail2ban для защиты SSH

```bash
sudo systemctl enable --now fail2ban
sudo systemctl status fail2ban --no-pager
```

Дефолтный jail для SSH включён сразу. Кастомные настройки — в
`/etc/fail2ban/jail.local` (если нужно изменить `findtime`/`bantime`).

---

## Установка Docker

Официальная инструкция Docker для Ubuntu 24.04:

```bash
# Удалить старые версии, если есть
sudo apt remove -y docker docker-engine docker.io containerd runc || true

# Добавить репозиторий Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Добавьте пользователя в группу `docker` (чтобы не писать `sudo docker` каждый раз):

```bash
sudo usermod -aG docker whoiswatcher
# Выйдите и зайдите заново, либо:
newgrp docker
docker ps   # должно работать без sudo
docker compose version
```

---

## Клонирование репозитория

### SSH-ключ для GitHub (deploy key)

Создайте отдельный SSH-ключ для сервера и подключите его как deploy-key в репозитории:

```bash
# На сервере
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -C "deploy@$(hostname)" -N ""
cat ~/.ssh/github_deploy.pub
```

Скопируйте вывод. В GitHub: репозиторий → **Settings → Deploy keys → Add deploy key**.
Имя — например, `production-server`. **Allow write access** — обычно НЕ нужно
(для деплоя достаточно чтения).

Настройте `~/.ssh/config`:

```sshconfig
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_deploy
    IdentitiesOnly yes
```

Проверка:

```bash
ssh -T git@github.com
# Ожидаемый ответ:
# Hi <username>/<repo>! You've successfully authenticated, but GitHub does not provide shell access.
```

### Клонирование

```bash
mkdir -p ~/projects
cd ~/projects
git clone git@github.com:<owner>/whois-watcher.git
cd whois-watcher
git log --oneline -5
```

---

## Настройка .env

```bash
cp .env.example .env
```

### Обязательные переменные

| Переменная | Откуда взять |
|------------|--------------|
| `BOT_TOKEN` | Создайте бота у [@BotFather](https://t.me/BotFather) в Telegram, скопируйте токен |
| `POSTGRES_PASSWORD` | Сгенерируйте: `openssl rand -hex 24` |
| `WEBHOOK_SECRET` | Сгенерируйте: `openssl rand -hex 32` |
| `WEBHOOK_BASE_URL` | `https://<ваш-домен>:8443` (без trailing slash) |
| `WEBHOOK_PATH` | `/webhook/<секрет>` — например, `/webhook/$(openssl rand -hex 16)` |

Удобный one-liner для генерации трёх случайных секретов сразу (без вывода в чат):

```bash
WEBHOOK_SECRET=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 24)
WEBHOOK_PATH="/webhook/$(openssl rand -hex 16)"
sed -i "s|^WEBHOOK_SECRET=.*|WEBHOOK_SECRET=${WEBHOOK_SECRET}|"   .env
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|" .env
sed -i "s|^WEBHOOK_PATH=.*|WEBHOOK_PATH=${WEBHOOK_PATH}|"          .env
unset WEBHOOK_SECRET POSTGRES_PASSWORD WEBHOOK_PATH
```

### Опциональные переменные

- `SENTRY_DSN` — оставьте пустым, если Sentry не используете.
- `ADMIN_CHANNEL_ID` — ID канала для алертов (формат `-100xxxxxxxxxx`). Если
  оставляете пустым — **закомментируйте строку**, иначе pydantic-settings
  попытается распарсить пустую строку как `int` и упадёт:
  ```
  # ADMIN_CHANNEL_ID=
  ```
- `ADMIN_USER_IDS` — список Telegram ID администраторов через запятую,
  напр. `12345,67890`. Пустая строка допустима.
- `BOT_NAME` — отображаемое имя бота. **Если содержит пробел — заключите в кавычки:**
  ```
  BOT_NAME="Whois Watcher"
  ```
  Docker Compose парсит env-файл корректно и без кавычек, но `source .env` в
  bash сломается на пробеле — это вылазит при ручной диагностике через
  `curl ... ${BOT_TOKEN} ...`.
- `WHOIS_PROXY_*` — см. [WHOIS proxy gateway](#whois-proxy-gateway-adr-028).

### Безопасность

- Файл `.env` находится в `.gitignore` — **никогда** не коммитьте.
- Доступ к файлу — только владельцу: `chmod 600 .env`.
- Не выводите содержимое `.env` в общедоступные логи/чаты.

---

## Подъём базы данных и Redis

```bash
cd ~/projects/whois-watcher
docker compose up -d postgres redis
```

Подождите 10–15 секунд (init Postgres + healthcheck), затем проверьте:

```bash
docker compose ps
# Ожидаем оба сервиса в статусе Up (healthy)

docker compose logs postgres --tail 20
docker compose logs redis    --tail 10
```

В логах Postgres должно быть:
```
LOG:  database system is ready to accept connections
```

В логах Redis:
```
* Ready to accept connections tcp
```

---

## Накат миграций

```bash
docker compose run --rm bot alembic upgrade head
```

Команда соберёт Docker-образ бота (первый запуск — несколько минут на
скачивание базового образа и установку зависимостей через `uv`; повторные —
секунды благодаря кэшу), затем выполнит миграции.

Ожидаемый вывод:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 20260515_init, initial schema
```

Проверка структуры БД:

```bash
docker compose exec postgres psql -U whoiswatcher -d whoiswatcher -c "\dt"
# Должно быть 7 таблиц: alembic_version + 6 наших (users, user_domains,
# whois_cache, sent_notifications, domain_changes, system_events)

docker compose exec postgres psql -U whoiswatcher -d whoiswatcher -c "\di"
# Среди индексов должен быть ix_whois_cache_next_check_at — критичен
# для производительности scheduler_tick.

docker compose run --rm bot alembic current
# Должен показать: 20260515_init (head)
```

---

## Запуск всех сервисов

```bash
docker compose up -d
docker compose ps
```

Должны быть **5 сервисов** в статусе `Up (healthy)`:

| Сервис | Назначение |
|--------|------------|
| `ww-postgres` | PostgreSQL 16 |
| `ww-redis` | Redis 7 |
| `ww-bot` | Webhook-сервер + хэндлеры команд |
| `ww-worker` | ARQ-воркеры (WHOIS-проверки, уведомления) |
| `ww-scheduler` | ARQ scheduler (cron `scheduler_tick` каждые 5 минут) |

Логи каждого:

```bash
docker compose logs bot       --tail 30
docker compose logs worker    --tail 30
docker compose logs scheduler --tail 30
```

В логах `bot` сразу после старта будет:
```
INFO  src.bot.webhook: Webhook set: https://<ваш-домен>:8443/webhook/<...>
======== Running on http://0.0.0.0:8080 ========
```

> **Замечание:** регистрация webhook происходит **до** настройки nginx/SSL.
> Telegram примет URL, но реальные апдейты не будут доходить, пока вы не
> поднимете reverse proxy. См. следующий раздел.

---

## Reverse proxy и SSL (nginx + Let's Encrypt)

Бот слушает HTTP на `127.0.0.1:8080` внутри docker-сети.
Снаружи нужен HTTPS на 8443 — поднимаем через nginx + Let's Encrypt.

### Установка

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo systemctl is-active nginx   # должно: active
nginx -v
certbot --version
```

### Временный server block для ACME challenge

Чтобы certbot мог пройти HTTP-01 challenge, нужен работающий HTTP на 80.

```bash
sudo tee /etc/nginx/sites-available/<ваш-домен>.conf > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name <ваш-домен>;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 404;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/<ваш-домен>.conf \
            /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Получение сертификата

> **ВНИМАНИЕ:** Let's Encrypt имеет rate-limit **5 сертификатов в неделю** на
> один домен. Не запускайте `certbot` в цикле «попробуем-ещё-раз» при ошибках —
> исправьте причину и повторите один раз.

```bash
sudo certbot certonly --webroot -w /var/www/html \
    -d <ваш-домен> \
    --email <ваш-email> \
    --agree-tos --no-eff-email \
    --non-interactive
```

После успеха:
```
Certificate is saved at: /etc/letsencrypt/live/<ваш-домен>/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/<ваш-домен>/privkey.pem
```

Если упало — сначала проверьте, что 80 порт реально доступен снаружи:
```bash
curl -I http://<ваш-домен>/
# Должен ответить 404 от nginx (наш заглушечный location /)
```

И смотрите детали в `/var/log/letsencrypt/letsencrypt.log` (последние 50 строк).

### Финальная конфигурация nginx

```bash
sudo tee /etc/nginx/sites-available/<ваш-домен>.conf > /dev/null <<'EOF'
# HTTP — редирект на HTTPS + поддержка ACME renewals
server {
    listen 80;
    listen [::]:80;
    server_name <ваш-домен>;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://$host:8443$request_uri;
    }
}

# HTTPS на 8443 — для Telegram webhook
server {
    listen 8443 ssl http2;
    listen [::]:8443 ssl http2;
    server_name <ваш-домен>;

    ssl_certificate     /etc/letsencrypt/live/<ваш-домен>/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/<ваш-домен>/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options nosniff always;

    client_max_body_size 10M;

    # Webhook — проксируем в бот
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;

        proxy_connect_timeout 10s;
        proxy_send_timeout    30s;
        proxy_read_timeout    30s;
    }

    # Healthcheck — без записи в access_log
    location = /health {
        proxy_pass http://127.0.0.1:8080/health;
        access_log off;
    }
}
EOF

sudo nginx -t
sudo systemctl reload nginx
```

### Проверки доступности

С самого сервера:

```bash
# HTTP 80 → 301 на HTTPS:8443
curl -I http://<ваш-домен>/

# HTTPS 8443 → /health отвечает 200
curl https://<ваш-домен>:8443/health
# Должен вернуть: {"status": "ok"}

# Параметры сертификата
echo | openssl s_client -connect <ваш-домен>:8443 \
    -servername <ваш-домен> 2>/dev/null | \
    openssl x509 -noout -dates -issuer -subject
# notBefore: текущая дата
# notAfter: ~3 месяца вперёд
# issuer: Let's Encrypt
# subject: CN = <ваш-домен>
```

### Авто-обновление сертификата

`certbot.timer` устанавливается и включается автоматически. Проверка:

```bash
sudo systemctl list-timers | grep certbot
# Должен быть timer, запускается ~раз в день

sudo certbot renew --dry-run
# Симуляция обновления; должно завершиться без ошибок
```

---

## Регистрация webhook в Telegram

**Отдельных действий не требуется** — бот сам делает `set_webhook` при старте
(см. `src/bot/webhook.py`). URL берётся из `WEBHOOK_BASE_URL + WEBHOOK_PATH`.

Если нужно принудительно перерегистрировать (например, после смены домена или
секрета):

```bash
docker compose restart bot
docker compose logs bot --tail 10
# Ожидаемая строка:
# INFO  src.bot.webhook: Webhook set: https://...
```

> **Подводный камень:** `docker compose restart` **не перечитывает** `env_file`.
> Если вы изменили `.env` — используйте `docker compose up -d` (compose
> пересоздаст контейнер, подхватив новый env). См. также
> [Troubleshooting → Изменения .env не применяются](#изменения-env-не-применяются).

Проверка регистрации через Telegram API:

```bash
set -a; source .env; set +a
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool
```

В ответе:
- `url` — должен совпадать с `WEBHOOK_BASE_URL + WEBHOOK_PATH`
- `pending_update_count` — обычно 0, если бот успевает обрабатывать
- `last_error_date` / `last_error_message` — **должны отсутствовать**. Если
  присутствуют — Telegram не может достучаться. Проверьте nginx, файрвол,
  SSL-сертификат.

---

## WHOIS proxy gateway (ADR 028)

С Этапа 10 бот ходит за WHOIS-данными через локальный proxy-gateway.
Прокси сам выбирает upstream (RDAP / WHOIS:43 / выделенный RU-relay для
`.ru/.рф/.su`) и кэширует ответы на 24 ч.

### Сетевая топология

Прокси-сервис (`/opt/whoisd/server.py`) работает на **хосте**, слушает
`127.0.0.1:8043`. Контейнеры бот/worker/scheduler имеют изолированный
network namespace — `127.0.0.1` внутри контейнера это loopback самого
контейнера, не хоста.

Чтобы контейнеры могли достучаться до прокси на хосте, в `docker-compose.yml`
для сервисов `bot`/`worker`/`scheduler` указано:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

— это стандартный Docker-механизм пробрасывания хоста в контейнерную
сеть. В `.env`:

```
WHOIS_PROXY_URL=http://host.docker.internal:8043
```

(Для прямого запуска `python -m src.main` без Docker — указывать
`http://127.0.0.1:8043`.)

Старый механизм `WHOIS_SERVER_OVERRIDES` (env с маппингом `tld → server`)
**удалён** — см. DEPRECATED [ADR 023](decisions.md#023-whois-server-overrides-per-tld-deprecated-in-v040)
и заменивший его [ADR 028](decisions.md#028-whois-proxy-gateway-as-primary-lookup).

### Если прокси упал

Симптом — в админ-канал прилетел алерт **«WHOIS proxy is down»**
(периодический cron `proxy_health_check` каждые 15 мин).

Диагностика:

```bash
curl -s http://127.0.0.1:8043/healthz       # должен вернуть 200 ok
systemctl status whoisd                      # если прокси крутится как сервис
journalctl -u whoisd -n 30 --no-pager        # последние логи
```

Что происходит с ботом, пока прокси лежит: автоматический fallback на
прямой `lookup_direct` (RDAP + WHOIS:43). Функциональность сохранена,
теряются только 24-часовой кеш и RU-relay (`.ru/.рф/.su` могут
не отвечать с зарубежных хостеров).

### Если бот собирается без прокси

В нестандартных деплоях (тесты, локалка без прокси) поставьте:

```
WHOIS_PROXY_ENABLED=false
```

— бот сразу пойдёт через `lookup_direct`, healthcheck отключится.

---

## Обновление до новой версии

Одна команда — `bash scripts/deploy.sh` — выполняет всё, что нужно:

```bash
cd ~/projects/whois-watcher
bash scripts/deploy.sh
```

Что делает скрипт по порядку:

1. **Проверка чистоты working tree** — отказ, если есть uncommitted-изменения.
2. **Сохранение текущего commit** в `.last-deployed-commit` (для будущего
   rollback).
3. **`git pull origin main`** — если HEAD не изменился, выходит с
   «Already up to date» (идемпотентный no-op).
4. **`scripts/generate_build_info.sh`** — пишет `src/_build_info.py`
   с новым commit/branch/tag/timestamp.
5. **`docker compose build bot worker scheduler`** — пересборка образа
   (кэш слоёв ускоряет если изменения локализованы).
6. **`alembic upgrade head`** — накат миграций (идемпотентно).
7. **`docker compose up -d bot worker scheduler`** — пересоздание трёх
   сервисов; postgres/redis не трогает.
8. **Wait for healthy** — поллит `docker compose ps` до 30с, пока
   healthcheck'и не позеленеют.
9. **HTTP-проверка** `/health` через `curl` — гарантирует, что бот
   реально отвечает на запросы.
10. **Финальный статус** — `docker compose ps` + последние 10 строк
    логов бота.

Скрипт `set -euo pipefail` — на любой ошибке прерывается с ненулевым кодом
возврата (удобно для cron / CI).

### Ручной режим (если деплой нужно сделать пошагово)

```bash
git pull origin main
bash scripts/generate_build_info.sh   # без этого /version покажет "unknown/dev"
docker compose build
docker compose run --rm bot alembic upgrade head
docker compose up -d
docker compose ps
docker compose logs bot --tail 30
```

Для откатки на предыдущий коммит:

```bash
git log --oneline -10
git checkout <commit-sha>
docker compose build
docker compose up -d
# Откат миграций (если новая версия их добавляла) — отдельно:
# docker compose run --rm bot alembic downgrade -1
```

---

## Troubleshooting

### Бот молчит после `/start`

1. **Логи бота:**
   ```bash
   docker compose logs bot --tail 50
   ```
   Ищите строки `aiohttp.access: ... "POST /webhook/..."`. Если их нет —
   Telegram не достучался до нас.

2. **Webhook info через Telegram API:**
   ```bash
   set -a; source .env; set +a
   curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool
   ```
   Смотрите `last_error_date`, `last_error_message`.

3. **TLS снаружи:**
   ```bash
   curl -v https://<ваш-домен>:8443/health
   ```
   Если ошибка SSL — проверьте срок жизни сертификата и nginx конфиг.

4. **Файрвол:**
   ```bash
   sudo ufw status
   # 8443/tcp должен быть ALLOW
   ```

### `/whois` для `.ru` / `.рф` не работает

Симптомы: ответ `network_error` или `timeout`.

Диагностика:

```bash
docker compose exec bot python3 -c "
import socket
s = socket.socket(); s.settimeout(5)
try:
    s.connect(('whois.tcinet.ru', 43))
    print('OK')
except Exception as e:
    print(f'FAIL: {e}')
"
```

Если `FAIL` — проверьте, что [WHOIS proxy gateway](#whois-proxy-gateway-adr-028)
поднят и `/healthz` отвечает 200: прокси сам ходит через RU-relay и
кэширует ответы.

### Контейнер не стартует

```bash
docker compose logs <service> --tail 80
```

Типичные причины:
- Пустое обязательное поле в `.env` (например, `BOT_TOKEN=`)
- Пустая строка в `int | None` поле (например, `ADMIN_CHANNEL_ID=` без значения
  и без комментирования) — pydantic-settings v2 пытается распарсить `""`
  как `int` и падает. Решение: закомментировать строку (`# ADMIN_CHANNEL_ID=`).
- Конфликт порта (`8080` уже занят другим процессом) — проверьте `ss -tlnp`.

### Изменения `.env` не применяются

`docker compose restart` **не перечитывает** `env_file`. Используйте:

```bash
docker compose up -d bot worker scheduler
```

Compose пересоздаст контейнеры с актуальным `.env`. Проверить, что env реально
применился:

```bash
docker compose exec bot env | grep WHOIS_PROXY
```

### Образ worker / scheduler устарел после `docker compose build bot`

Когда вы пересобираете один сервис (`build bot`), tag `whois-watcher:latest`
обновляется, но **запущенные контейнеры** `worker` и `scheduler` продолжают
работать на старом image ID. Чтобы они подхватили новый код:

```bash
docker compose up -d worker scheduler
```

Проверить hash:

```bash
docker compose images bot worker scheduler
# IMAGE ID у всех трёх должен совпадать
```

### Миграция Alembic упала

```bash
# Текущая ревизия
docker compose run --rm bot alembic current

# История миграций
docker compose run --rm bot alembic history

# Подробный лог последней попытки
docker compose run --rm bot alembic upgrade head 2>&1 | tail -50
```

Типичные причины:
- БД не запущена / неправильный DSN → проверьте `docker compose ps postgres`
  и `POSTGRES_*` переменные в `.env`.
- Сломанная история миграций (конфликт ревизий) → `alembic heads` покажет,
  если есть несколько head'ов.

### Сертификат Let's Encrypt не обновляется

```bash
sudo systemctl status certbot.timer
sudo systemctl list-timers | grep certbot
sudo certbot renew --dry-run
```

Если `--dry-run` падает — смотрите `/var/log/letsencrypt/letsencrypt.log`.
Самая частая причина — поломанный nginx-конфиг (ACME challenge не доходит).

### `source .env` падает с `command not found`

Признак: bash интерпретирует значение со значащим пробелом как команду:
```
.env: line N: Watcher: command not found
```

Причина: значение содержит пробел и не заключено в кавычки. Docker Compose
парсит такое корректно, bash — нет. Заключите в кавычки:
```
BOT_NAME="Whois Watcher"
```

---

## Безопасность

### Что НЕ коммитить

- **`.env`** (в `.gitignore` по умолчанию; есть только `.env.example`).
- Любые SSH-ключи, токены, сертификаты.
- Бэкапы БД с реальными данными пользователей.

### Минимальный набор хорошей гигиены

1. **SSH только по ключам** — отключите парольную авторизацию:
   ```bash
   sudo sed -i 's|^#*PasswordAuthentication .*|PasswordAuthentication no|' /etc/ssh/sshd_config
   sudo systemctl reload ssh
   ```
2. **fail2ban** на SSH (включён в этой инструкции).
3. **ufw** с минимальным набором портов (22/80/443/8443).
4. **Регулярные обновления:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
5. **Бот публикует webhook-порт только на localhost** — внешние подключения
   только через nginx с TLS. В `docker-compose.yml` это `127.0.0.1:8080:8080`.
6. **WEBHOOK_PATH** — должен включать случайный сегмент (например,
   `/webhook/<32 hex символа>`). Это второй фактор аутентификации Telegram-апдейтов
   помимо `WEBHOOK_SECRET` в заголовке.
7. **`chmod 600 .env`** — файл доступен только владельцу.

### Watchtower для авто-обновления контейнеров (опционально)

[Watchtower](https://containrrr.dev/watchtower/) автоматически обновляет
запущенные контейнеры, когда выходит новый тег их образа. Полезно для
обновления Postgres/Redis между минорными версиями. Бот / worker / scheduler
тегированы как `whois-watcher:latest` — для них обновление пойдёт после
`git pull && docker compose build`, watchtower не нужен.

---

## Архитектурные особенности

Полная архитектура — в [architecture.md](architecture.md). Здесь — только
тонкости, важные при деплое.

### Почему 8443, а не 443

Telegram принимает webhook только на портах **80, 88, 443, 8443**. На нашем
тестовом сервере 443 был занят другим сервисом (xray VPN), поэтому
использовали 8443 — это разрешённая Telegram альтернатива. Если у вас 443
свободен — можно использовать его, тогда поправьте `WEBHOOK_BASE_URL` и
nginx-конфиг.

### Почему RDAP + WHOIS:43 fallback

RDAP — современный JSON-стандарт поверх HTTPS:443. Работает почти всегда
(порт 443 не блокируют). Покрывает большинство gTLD (`.com`, `.org`, `.io`,
`.app`, `.dev`).

WHOIS:43 — старый текстовый протокол. Нужен для ccTLD, где RDAP пока не
поддержан (`.ru`, `.рф`, `.de`, `.it` и др.). Раньше блокировки портов
решались через `WHOIS_SERVER_OVERRIDES`; теперь — через
[WHOIS proxy gateway](#whois-proxy-gateway-adr-028).

Подробности — в [ADR 008](decisions.md#008-rdap-как-основной-протокол-whois-как-fallback).

### Почему адаптивный TTL

Дата истечения домена почти не меняется. Проверять все 50 000 доменов
пользователя каждый день — расточительно. Адаптивный TTL: чем ближе к
истечению, тем чаще проверка (от раз в 30 дней до раз в день). Конкретные
интервалы — в `src/config/limits.py` и [ADR 007](decisions.md#007-адаптивный-ttl-проверок).

### Три независимых процесса

`bot` / `worker` / `scheduler` — отдельные контейнеры, общаются через
PostgreSQL и Redis (для ARQ-очереди). Это значит:

- Падение worker не валит bot и наоборот.
- Воркеров можно масштабировать горизонтально (поднять второй
  `ww-worker-2` на том же образе с тем же `command`).
- Scheduler должен быть **один** — иначе cron-задачи дублируются.

Подробнее — [ADR 009](decisions.md#009-три-независимых-процесса).
