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
                         └── Traefik UI     (traefik-dashboard.2dep.duckdns.org)

CoreDNS (172.30.0.212:53) — локальный DNS, резолвит *.2dep.duckdns.org → 172.30.0.212

Prometheus scrapes:
  - node-exporter         — метрики хоста
  - cadvisor              — метрики Docker контейнеров
  - traefik               — метрики reverse proxy
  - snmp-exporter         — SNMP метрики сетевого оборудования (10.5.10.91, 10.5.141.2)
  - fusionpbx             — VoIP метрики (172.30.0.210, 172.30.0.195) через кастомный /metrics.txt
  - freeswitch-exporter   — FreeSWITCH метрики через ESL (172.30.0.201, .197, .207, .214, .215)

Loki — сбор логов, retention 14 дней
```

## Сервисы

| Сервис | Образ | Назначение |
|--------|-------|-----------|
| traefik | traefik:v3.0 | Reverse proxy + SSL (DuckDNS challenge) |
| coredns | coredns/coredns | Локальный DNS для LAN |
| grafana | grafana/grafana | Дашборды мониторинга |
| prometheus | prom/prometheus | Time-series БД метрик (retention 15d/20GB) |
| loki | grafana/loki | Агрегация логов (retention 14d) |
| node-exporter | prom/node-exporter | Метрики хоста |
| snmp-exporter | prom/snmp-exporter | SNMP метрики (порт 9116) |
| cadvisor | gcr.io/cadvisor | Метрики контейнеров |
| uptime-kuma | louislam/uptime-kuma:2 | Мониторинг доступности |
| vaultwarden | vaultwarden/server | Менеджер паролей (Bitwarden-совместимый) |
| freeswitch-exporter | custom (Python) | FreeSWITCH метрики через ESL, multi-target (порт 9724) |

## TV Kiosk

KIVI TV (Android 11, 172.30.1.129:5555 ADB) отображает Grafana дашборд через **WallPanel**.

- Приложение: `xyz.wallpanel.app`
- Dashboard URL: `https://grafana.2dep.duckdns.org/d/freeswitch-tv?kiosk`
- Пользователь Grafana: `monitoring`
- WallPanel REST API: `http://172.30.1.129:2971`

Подробнее: [docs/TV_KIOSK.md](docs/TV_KIOSK.md)

## Grafana Dashboards

| Dashboard | UID | Назначение |
|-----------|-----|-----------|
| FreeSWITCH Overview | `freeswitch-overview` | Детальный дашборд для анализа (графики, таблицы) |
| FreeSWITCH TV | `freeswitch-tv` | TV kiosk — статус кластера одним взглядом |

Оба дашборда провижонятся из `grafana/dashboards/` через `grafana/provisioning/dashboards/dashboards.yml`.

### FreeSWITCH TV — панели

- **Uptime** — время работы каждого сервера (красный <1ч, оранжевый <1д)
- **Server Status** — UP/DOWN по серверам
- **Registrations** — количество активных регистраций
- **Active Calls / Channels** — текущая нагрузка
- **Failed Calls (1h)** — рост ошибок за последний час
- **Gateways** — статус каждого гейтвея (цветные блоки UP/DOWN)

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
grafana/dashboards/freeswitch-overview.json     — Grafana дашборд FreeSWITCH (детальный)
grafana/dashboards/freeswitch-tv.json           — Grafana дашборд FreeSWITCH (TV kiosk)
grafana/provisioning/dashboards/dashboards.yml  — provisioning дашбордов
.env                                            — секреты (DUCKDNS_TOKEN, GRAFANA_USER/PASSWORD, FREESWITCH_ESL_PASSWORD)
```

## Важные особенности

- Traefik использует **DuckDNS DNS challenge** для wildcard сертификата `*.2dep.duckdns.org`
- CoreDNS резолвит все поддомены `2dep.duckdns.org` → `172.30.0.212` локально (без выхода в интернет)
- Prometheus защищён basic auth через Traefik middleware `traefik-auth`
- Play Store (`com.android.vending`) на TV отключён через `pm disable-user` для экономии RAM
