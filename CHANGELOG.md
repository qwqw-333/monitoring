# Changelog

Все значимые изменения в этом проекте будут документироваться в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
и этот проект придерживается [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Добавлено
- Поддержка позиционных аргументов для команд `up`, `down`, `restart` и `logs` в Makefile
  - Теперь можно использовать `make restart traefik` вместо `make restart SERVICE_NAME=traefik`
  - Команды работают как с аргументом (конкретный сервис), так и без него (все сервисы)

## [1.0.0] - 2025-11-08

### Добавлено

#### Основные компоненты
- Traefik как reverse proxy с автоматическими SSL сертификатами через DuckDNS
- CoreDNS для локального DNS резолвинга
- Uptime Kuma для мониторинга доступности сервисов
- Vaultwarden как менеджер паролей (совместим с Bitwarden)
- SigNoz для observability (метрики, трейсы, логи)
- ClickHouse как хранилище данных для SigNoz
- Zookeeper для координации ClickHouse

#### Инфраструктура и инструменты
- Docker Compose конфигурация для всех сервисов
- Healthchecks для всех основных сервисов (Traefik, CoreDNS, Uptime Kuma, Vaultwarden, SigNoz OTEL Collector)
- Makefile с удобными командами для управления стеком
- Документация по настройке всех компонентов
- CHANGELOG.md для отслеживания изменений
- LICENSE файл (MIT)

[1.0.0]: https://github.com/yourusername/monitoring/releases/tag/v1.0.0
