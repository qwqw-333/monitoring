# Быстрый старт

## 1. Получите токен Duck DNS

1. Зайдите на https://www.duckdns.org
2. Войдите через GitHub/Google
3. Скопируйте **API Token**

## 2. Файл .env

```bash
echo "DUCKDNS_API_TOKEN=ваш-токен" > .env
```
```bash
echo $(htpasswd -nB user) | sed -e s/\\$/\\$\\$/g
```

## 3. Настройте поддомены в Duck DNS

На https://www.duckdns.org добавьте поддомены:
- `kuma` → `kuma.example.duckdns.org`
- `vault` → `vault.example.duckdns.org`
- `signoz` → `signoz.example.duckdns.org`

## 4. Обновите IP адрес

```bash
# Узнайте ваш публичный IP
curl ifconfig.me

# Обновите в Duck DNS (замените example на ваш домен)
curl "https://www.duckdns.org/update?domains=example&token=YOUR_TOKEN&ip=YOUR_IP"
```

## 5. Запустите сервисы

```bash
docker compose up -d
```

## 6. Настройте Nginx Proxy Manager

1. Откройте `http://YOUR_SERVER_IP:81`
2. Создайте аккаунт администратора
3. Настройте SSL сертификаты и proxy hosts (см. [NGINX_PROXY_MANAGER_SETUP.md](NGINX_PROXY_MANAGER_SETUP.md))

## Готово!

Сервисы доступны по адресам:
- https://kuma.example.duckdns.org
- https://vault.example.duckdns.org
- https://signoz.example.duckdns.org
