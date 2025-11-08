# Инфраструктура мониторинга

Self-hosted инфраструктура для мониторинга, observability и управления паролями с автоматическими SSL сертификатами.

## Компоненты

- **Nginx Proxy Manager** - reverse proxy с веб-интерфейсом
- **CoreDNS** - локальный DNS сервер для закрытого окружения
- **Uptime Kuma** - мониторинг доступности сервисов
- **Vaultwarden** - менеджер паролей (совместим с Bitwarden)
- **Signoz** - платформа observability (метрики, трейсы, логи)

## Быстрый старт

1. **Настройте Duck DNS** (см. [QUICKSTART.md](docs/QUICKSTART.md))
2. **Запустите сервисы:**
   ```bash
   docker compose up -d
   ```
3. **Настройте Nginx Proxy Manager:**
   - Откройте `http://YOUR_SERVER_IP:81`
   - Создайте аккаунт администратора
   - Настройте SSL сертификаты и proxy hosts (см. [NGINX_PROXY_MANAGER_SETUP.md](docs/NGINX_PROXY_MANAGER_SETUP.md))

## Документация

- [QUICKSTART.md](docs/QUICKSTART.md) - быстрый старт
- [DUCKDNS_SETUP.md](docs/DUCKDNS_SETUP.md) - подробная настройка Duck DNS
- [COREDNS_SETUP.md](docs/COREDNS_SETUP.md) - настройка CoreDNS для локального DNS
- [NGINX_PROXY_MANAGER_SETUP.md](docs/NGINX_PROXY_MANAGER_SETUP.md) - настройка Nginx Proxy Manager

## Структура проекта

```
monitoring/
├── compose.yaml              # Docker Compose конфигурация
├── coredns/                  # Конфигурация CoreDNS
│   └── Corefile.template     # Шаблон конфигурации (использует переменную DOMAIN)
├── signoz-config/            # Конфигурация Signoz и ClickHouse
│   ├── collector-config.yaml # Конфигурация OTEL Collector
│   ├── clickhouse/           # Конфигурация ClickHouse
│   ├── signoz/               # Конфигурация Signoz
│   └── dashboards/           # Дашборды
└── docs/                     # Документация
```

## Доступ к сервисам

После настройки доступны по адресам:
- **Uptime Kuma**: `https://kuma.example.duckdns.org`
- **Vaultwarden**: `https://vault.example.duckdns.org`
- **Signoz**: `https://signoz.example.duckdns.org`

## Полезные команды

```bash
# Просмотр логов
docker compose logs -f

# Перезапуск сервисов
docker compose restart

# Остановка
docker compose down
```
