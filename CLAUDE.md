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
  - fusionpbx             — VoIP метрики (172.30.0.210) через кастомный /metrics.txt (legacy)
  - freeswitch-exporter   — FreeSWITCH метрики через ESL (172.30.0.195, .201, .197, .207, .214, .215)

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

| Dashboard | UID | Назначение |
|-----------|-----|-----------|
| VoIP TV | `adzvr2k` | TV kiosk — статус кластера одним взглядом |

Дашборд хранится в базе Grafana (не provisioned) и редактируется через веб-интерфейс.

### VoIP TV — панели

- **Uptime** — время работы каждого сервера (красный <1ч, оранжевый <1д)
- **Server Status** — UP/DOWN по серверам
- **Registrations** — количество активных регистраций
- **Active Calls / Channels** — текущая нагрузка
- **Failed Calls (1h)** — рост неуспешных SIP-транзакций через гейтвеи за час
- **Gateways** — статус гейтвеев по строкам (Kv UMZ, Kv Gate, Gate0, Spas, Int Gate, WG0)

### Мониторируемые серверы

| server_name | IP | Тип |
|-------------|-----|-----|
| Kv UMZ | 172.30.0.195 | FusionPBX (production, ~860 регистраций) |
| Kv Gate | 172.30.0.207 | FreeSWITCH standalone |
| Gate0 | 172.30.0.197 | FreeSWITCH standalone |
| Spas | 172.30.0.214 | FreeSWITCH standalone |
| Int Gate | 172.30.0.215 | FreeSWITCH standalone |
| WG0 | 172.30.0.201 | FreeSWITCH standalone |

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
.env                                            — секреты (DUCKDNS_TOKEN, FREESWITCH_ESL_PASSWORD)
```

## Важные особенности

- Traefik использует **DuckDNS DNS challenge** для wildcard сертификата `*.2dep.duckdns.org`
- CoreDNS резолвит все поддомены `2dep.duckdns.org` → `172.30.0.212` локально (без выхода в интернет)
- Prometheus защищён basic auth через Traefik middleware `traefik-auth`
- Play Store (`com.android.vending`) на TV отключён через `pm disable-user` для экономии RAM
