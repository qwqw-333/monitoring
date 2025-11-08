# Настройка Duck DNS

Duck DNS предоставляет бесплатные домены для работы за NAT без публичного IP.

## Преимущества

✅ Валидные SSL сертификаты от Let's Encrypt  
✅ Работает за NAT  
✅ Автоматическое обновление сертификатов  
✅ Не требует установки CA на устройствах

## Шаг 1: Получение токена

1. Зайдите на https://www.duckdns.org
2. Войдите через GitHub или Google
3. Выберите или создайте домен (например, `example`)
4. Скопируйте **API Token**

## Шаг 2: Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```bash
DUCKDNS_API_TOKEN=your-duckdns-token-here
```

## Шаг 3: Создание поддоменов

В Duck DNS добавьте поддомены:
- `kuma` → `kuma.example.duckdns.org`
- `vault` → `vault.example.duckdns.org`
- `signoz` → `signoz.example.duckdns.org`

## Шаг 4: Обновление IP адреса

### Вручную

```bash
# Узнайте публичный IP
curl ifconfig.me

# Обновите в Duck DNS (замените example на ваш домен)
curl "https://www.duckdns.org/update?domains=example&token=YOUR_TOKEN&ip=YOUR_IP"
```

### Автоматически (cron)

Создайте скрипт `update-duckdns.sh`:

```bash
#!/bin/bash
DUCKDNS_TOKEN="your-token"
DUCKDNS_DOMAIN="example"  # Замените на ваш домен
PUBLIC_IP=$(curl -s ifconfig.me)
curl -s "https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=${PUBLIC_IP}"
```

Добавьте в crontab (обновление раз в день):

```bash
0 0 * * * /path/to/update-duckdns.sh
```

## Проверка работы

```bash
# Проверка DNS
nslookup kuma.example.duckdns.org

# Проверка SSL сертификата
openssl s_client -connect kuma.example.duckdns.org:443 -servername kuma.example.duckdns.org < /dev/null 2>/dev/null | openssl x509 -noout -issuer
```

Должен показать: `issuer= /CN=R3` (Let's Encrypt)

## Troubleshooting

**DNS не резолвится:**
- Убедитесь, что поддомены созданы в Duck DNS
- Проверьте, что IP адрес обновлен
- Подождите несколько минут для распространения DNS

**Сертификат не получается:**
- Проверьте токен в `.env`
- Убедитесь, что поддомены созданы
- Проверьте логи: `docker compose logs nginx-proxy-manager`

## Примечания

- Duck DNS требует обновления IP минимум раз в месяц
- Сертификаты Let's Encrypt действительны 90 дней и обновляются автоматически
