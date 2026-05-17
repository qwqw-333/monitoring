# CLAUDE.md — Контекст проекта

## Обзор

Self-hosted мониторинг-стек на базе Docker Compose. Сервер: `172.30.0.212`, домен: `2dep.duckdns.org` (DuckDNS + Let's Encrypt wildcard через Traefik).

## Архитектура

```
Internet → Traefik (443) → внутренняя сеть Docker (internal)
                         ├── Grafana        (grafana.2dep.duckdns.org)
                         ├── Prometheus     (prometheus.2dep.duckdns.org)
                         ├── Uptime Kuma    (kuma.2dep.duckdns.org)
                         ├── Vaultwarden    (vault.2dep.duckdns.org)
                         ├── ntfy           (ntfy.2dep.duckdns.org)
                         └── Traefik UI     (traefik-dashboard.2dep.duckdns.org)

CoreDNS (172.30.0.212:53) — локальный DNS, резолвит *.2dep.duckdns.org → 172.30.0.212

Prometheus scrapes:
  - node-exporter         — метрики хоста
  - cadvisor              — метрики Docker контейнеров
  - traefik               — метрики reverse proxy
  - snmp-exporter         — SNMP метрики Grandstream оборудования
  - kv umz                — VoIP метрики (172.30.0.195) через /metrics.txt (legacy)
  - freeswitch-exporter   — FreeSWITCH метрики через ESL (9 серверов)

Loki — сбор событий регистрации UMZ, retention 1 год
  umz-event-detector → Loki (job="umz-events", logfmt)
```

## Сервисы

| Сервис | Образ | Назначение |
|--------|-------|-----------|
| traefik | traefik:v3 | Reverse proxy + SSL (DuckDNS challenge) |
| coredns | coredns/coredns:1.13.1 | Локальный DNS для LAN |
| grafana | grafana/grafana:12.3.0 | Дашборды мониторинга |
| prometheus | prom/prometheus:v3.7 | Time-series БД метрик (retention 15d/20GB) |
| loki | grafana/loki:3.6.2 | Агрегация логов (retention 1y) |
| node-exporter | prom/node-exporter:v1.10 | Метрики хоста |
| snmp-exporter | prom/snmp-exporter:v0.30.0 | SNMP метрики (порт 9116) |
| cadvisor | gcr.io/cadvisor/cadvisor:v0.49.1 | Метрики контейнеров |
| uptime-kuma | louislam/uptime-kuma:2 | Мониторинг доступности |
| vaultwarden | vaultwarden/server:1.33.2 | Менеджер паролей (Bitwarden-совместимый) |
| freeswitch-exporter | custom (Python) | FreeSWITCH метрики через ESL, multi-target (порт 9724) |
| umz-event-detector | custom (Python) | Real-time детектор событий регистрации UMZ → Loki (постоянные ESL-соединения) |
| ntfy | binwiederhier/ntfy:v2.21.0 | Self-hosted push-уведомления (через Traefik) |

## Доступ к Grafana

| Способ | URL |
|--------|-----|
| Через домен (Traefik + TLS) | `https://grafana.2dep.duckdns.org` |
| Через IP (LAN, без TLS) | `http://172.30.0.212:3000` |

## TV Kiosk

KIVI TV (Android 11, 172.30.1.129:5555 ADB) отображает Grafana дашборд через **WallPanel**.

- Приложение: `xyz.wallpanel.app`
- Dashboard URL: `https://grafana.2dep.duckdns.org/d/adzvr2k/voip-tv?kiosk`
- Пользователь Grafana: `monitoring`
- WallPanel REST API: `http://172.30.1.129:2971`

Подробнее: [docs/TV_KIOSK.md](docs/TV_KIOSK.md)

## Grafana Dashboard

Все дашборды provisioned из `grafana/dashboards/`, редактируемые (allowUiUpdates: true).

| Файл | Назначение |
|------|-----------|
| `umz-extentions.json` | Поиск экстеншена: текущий сервер/IP + лог событий (Loki) |
| `umz-reg-status.json` | Статус регистраций по 4 UMZ серверам |
| `kv-gateways-status.json` | Статус гейтвеев Kv UMZ |

VoIP TV дашборд (UID `adzvr2k`) хранится в базе Grafana и редактируется через веб-интерфейс (TV kiosk).

### VoIP TV — панели

- **Uptime** — время работы каждого сервера (красный <1ч, оранжевый <1д)
- **Server Status** — UP/DOWN по серверам
- **Registrations** — количество активных регистраций
- **Active Calls** — текущие активные вызовы по серверам
- **Registrations Kv UMZ** — time series график количества зарегистрированных абонентов на Kv UMZ
- **Gateways** — статус гейтвеев по строкам (Kv UMZ, Kv Gate, Gate0, Spas, Int Gate, WG0)

### UMZ Extension Events (Loki)

Сервис `umz-event-detector` держит **постоянные ESL-соединения** к 4 UMZ серверам и получает события регистрации в реальном времени (задержка < 1 сек). Подписка: `sofia::register / sofia::unregister / sofia::expire`.

- **Stream labels:** `job="umz-events"`, `event_type`, `level`, `server`
- **Формат логов:** logfmt
- **События:**

| event_type | level | Поля | Условие |
|------------|-------|------|---------|
| `register` | INFO | extension, ip | Новый абонент (не зарегистрирован нигде) |
| `offline` | WARN | extension, ip | Абонент пропал со всех серверов |
| `migrate` | INFO | extension, from, to, ip | Абонент стабильно переехал на другой сервер |

#### Логика детекции

- **SRV-bounce** (телефон кратковременно попал на другой сервер из-за DNS SRV и вернулся) — **подавляется**, событий нет.
- **Реальная миграция** — `migrate` эмитируется с задержкой `MIGRATE_CONFIRM_SECONDS=300` (5 мин) после того, как expire на старом сервере подтверждён и телефон всё ещё на новом.
- **Bounce detection**: если expire приходит с сервера, на который телефон мигрировал (`to_server`), — это bounce, pending_migrate удаляется без события.

#### Переменные окружения

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `MIGRATE_BUFFER_SECONDS` | `3` | Буфер expire-before-register корреляции |
| `MIGRATE_CONFIRM_SECONDS` | `300` | Задержка подтверждения реальной миграции (> max SIP expire) |
| `RECONNECT_DELAY` | `5` | Начальная пауза переподключения (с) |
| `RECONNECT_MAX_DELAY` | `60` | Максимальная пауза (экспоненциальный backoff) |

> `MIGRATE_CONFIRM_SECONDS` должен быть больше максимального SIP expire timeout. В текущей среде: sip_force_expire=60s, lifetime=120-150s → значение 300s.

**Пример запроса Grafana:**
```
{job="umz-events"} | logfmt | extension="45907"
```

### Мониторируемые серверы

| server_name | IP | Тип |
|-------------|-----|-----|
| Kv UMZ | 172.30.0.195 | FusionPBX (production, ~860 регистраций) |
| Kv Gate | 172.30.0.207 | FreeSWITCH standalone |
| Gate0 | 172.30.0.197 | FreeSWITCH standalone |
| Spas | 172.30.0.214 | FreeSWITCH standalone |
| Int Gate | 172.30.0.215 | FreeSWITCH standalone |
| Lv UMZ | 172.30.2.195 | FusionPBX (production) |
| Dn UMZ | 172.30.4.195 | FusionPBX (production) |
| Od UMZ | 172.30.8.195 | FusionPBX (production) |
| WG0 | 172.30.0.201 | FreeSWITCH standalone |

## ntfy (Push-уведомления)

Self-hosted сервер push-уведомлений для алертинга дежурным.

| Способ | URL |
|--------|-----|
| Через домен (Traefik + TLS) | `https://ntfy.2dep.duckdns.org` |

Конфиг: `ntfy/server.yml` (auth по умолчанию deny-all).

### Первоначальная настройка

```bash
# Создать admin-пользователя
docker exec -it ntfy ntfy user add --role=admin admin

# Создать топик для алертов и дать доступ
docker exec -it ntfy ntfy access admin alerts rw
```

### Использование

```bash
# Отправить тестовое уведомление
curl -u admin:PASSWORD -d "Test alert" https://ntfy.2dep.duckdns.org/alerts

# С приоритетом и тегами
curl -u admin:PASSWORD \
  -H "Priority: urgent" \
  -H "Tags: warning" \
  -H "Title: FreeSWITCH DOWN" \
  -d "Kv UMZ (172.30.0.195) не отвечает" \
  https://ntfy.2dep.duckdns.org/alerts
```

### Интеграция с Grafana Alerting

В Grafana → Alerting → Contact Points → Add → Webhook:
- URL: `http://ntfy:80/alerts`
- HTTP Method: POST
- Authorization: Basic auth (admin:PASSWORD)

Мобильное приложение: Android (Google Play / F-Droid), iOS — подписаться на `https://ntfy.2dep.duckdns.org/alerts`.

## Ключевые команды

```bash
# Статус сервисов
docker compose ps

# Перезапуск всего стека
docker compose up -d

# Логи конкретного сервиса
docker compose logs -f grafana

# Перезагрузить конфиг Prometheus без рестарта
curl -X POST http://localhost:9090/-/reload

# Управление TV через WallPanel API
curl -X POST http://172.30.1.129:2971/api/command \
  -H 'Content-Type: application/json' \
  -d '{"cmd": "reload"}'
```

## Конфигурационные файлы

```
compose.yaml                                   — все сервисы
prometheus/prometheus.yml                       — scrape targets
loki/local-config.yaml                          — конфиг Loki
coredns/Corefile                                — DNS зоны и хосты
snmp/snmp.yml                                   — SNMP модули
freeswitch-exporter/exporter.py                 — кастомный FreeSWITCH экспортёр (ESL → Prometheus)
freeswitch-exporter/event_detector.py           — real-time детектор событий регистрации (ESL event subscription → Loki)
grafana/provisioning/datasources/datasources.yaml — Prometheus + Loki datasources
grafana/provisioning/dashboards/dashboards.yml  — provisioning конфиг
grafana/dashboards/                             — provisioned JSON дашборды
ntfy/server.yml                                 — конфиг ntfy (push-уведомления)
.env                                            — секреты (DUCKDNS_TOKEN, FREESWITCH_ESL_PASSWORD)
```

## Важные особенности

- Traefik использует **DuckDNS DNS challenge** для wildcard сертификата `*.2dep.duckdns.org`
- CoreDNS резолвит все поддомены `2dep.duckdns.org` → `172.30.0.212` локально (без выхода в интернет)
- Prometheus защищён basic auth через Traefik middleware `traefik-auth`
- Play Store (`com.android.vending`) на TV отключён через `pm disable-user` для экономии RAM
