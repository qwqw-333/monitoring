# Быстрый старт

## 1. Получите токен Duck DNS

1. Зайдите на https://www.duckdns.org
2. Войдите через GitHub/Google
3. Скопируйте **API Token**

## 2. Файл .env

```bash
cat > .env <<EOF
DUCKDNS_TOKEN=ваш-токен
ACME_EMAIL=ваш@email.com
DOMAIN=example.duckdns.org
GRAFANA_USER=admin
GRAFANA_PASSWORD=секретный-пароль
TRAEFIK_AUTH=user:$$apr1$$...  # htpasswd -nB user
EOF
```

Генерация хэша пароля для Traefik:

```bash
echo $(htpasswd -nB user) | sed -e s/\\$/\\$\\$/g
```

## 3. Настройте поддомены в Duck DNS

На https://www.duckdns.org добавьте поддомен `2dep` (или свой) и укажите IP сервера.

## 4. Запустите сервисы

```bash
docker compose up -d
```

## 5. Проверьте статус

```bash
make ps
# или
docker compose ps
```

## Готово!

Сервисы доступны по адресам:

| Сервис | URL |
|--------|-----|
| Grafana | https://grafana.example.duckdns.org |
| Prometheus | https://prometheus.example.duckdns.org |
| Uptime Kuma | https://kuma.example.duckdns.org |
| Vaultwarden | https://vault.example.duckdns.org |
| Traefik Dashboard | https://traefik-dashboard.example.duckdns.org |

> Замените `example` на ваш реальный поддомен DuckDNS.
