# Инфраструктура мониторинга

Self-hosted стек мониторинга на базе Docker Compose с автоматическими SSL сертификатами через DuckDNS.

## Компоненты

| Сервис | Адрес | Назначение |
|--------|-------|-----------|
| **Traefik** | `traefik-dashboard.2dep.duckdns.org` | Reverse proxy + SSL |
| **Grafana** | `grafana.2dep.duckdns.org` | Дашборды |
| **Prometheus** | `prometheus.2dep.duckdns.org` | Метрики |
| **Loki** | внутренний | Логи |
| **Uptime Kuma** | `kuma.2dep.duckdns.org` | Мониторинг доступности |
| **Vaultwarden** | `vault.2dep.duckdns.org` | Менеджер паролей |
| **CoreDNS** | `172.30.0.212:53` | Локальный DNS |

Метрики собираются с: хоста (node-exporter), Docker (cadvisor), Traefik, SNMP-оборудования, FusionPBX.

## Быстрый старт

1. Скопируй `.env` и заполни переменные:
   ```
   DUCKDNS_TOKEN=your-token
   DOMAIN=your-domain.duckdns.org
   GRAFANA_USER=admin
   GRAFANA_PASSWORD=secret
   ```

2. Запусти стек:
   ```bash
   docker compose up -d
   ```

## TV Kiosk

KIVI TV отображает Grafana дашборд через WallPanel (kiosk-браузер).
Управление через REST API: `http://172.30.1.129:2971`

Подробнее: [docs/TV_KIOSK.md](docs/TV_KIOSK.md)

## Документация

- [docs/TV_KIOSK.md](docs/TV_KIOSK.md) — TV kiosk: WallPanel, ADB, REST API
- [docs/DUCKDNS_SETUP.md](docs/DUCKDNS_SETUP.md) — настройка DuckDNS
- [docs/COREDNS_SETUP.md](docs/COREDNS_SETUP.md) — настройка CoreDNS

## Полезные команды

```bash
# Статус
docker compose ps

# Логи
docker compose logs -f grafana

# Перезагрузить конфиг Prometheus
curl -X POST http://localhost:9090/-/reload

# Reload TV дашборда
curl -X POST http://172.30.1.129:2971/api/command \
  -H 'Content-Type: application/json' \
  -d '{"cmd": "reload"}'
```
