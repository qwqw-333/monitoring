# Настройка Nginx Proxy Manager

Nginx Proxy Manager предоставляет веб-интерфейс для управления reverse proxy и SSL сертификатами.

## Быстрый старт

1. Запустите сервисы:
   ```bash
   docker compose up -d
   ```

2. Откройте веб-интерфейс:
   - URL: `http://YOUR_SERVER_IP:81`
   - Email: `admin@example.com`
   - Password: `changeme` (измените при первом входе)

## Настройка SSL сертификата через Duck DNS

### Шаг 1: Создайте DNS Credentials

1. Перейдите в **SSL Certificates** → **Add SSL Certificate**
2. Выберите **Let's Encrypt** → **Use a DNS Challenge**
3. В поле **DNS Provider** выберите **Duck DNS** или **Other**
4. В поле **Credentials File Content** введите:
   ```
   dns_duckdns_token=ваш-токен-из-env-файла
   ```
5. В поле **Domain Names** укажите домены (каждый с новой строки):
   ```
   kuma.example.duckdns.org
   vault.example.duckdns.org
   signoz.example.duckdns.org
   ```
   Или для wildcard:
   ```
   *.example.duckdns.org
   example.duckdns.org
   ```
6. Нажмите **Save**

### Шаг 2: Создайте Proxy Hosts

Для каждого сервиса создайте Proxy Host:

#### Uptime Kuma

1. **Proxy Hosts** → **Add Proxy Host**
2. **Details:**
   - **Domain Names:** `kuma.example.duckdns.org`
   - **Scheme:** `http`
   - **Forward Hostname/IP:** `uptime-kuma`
   - **Forward Port:** `3001`
   - Включите **Block Common Exploits** и **Websockets Support**
3. **SSL:**
   - **SSL Certificate:** Выберите созданный сертификат
   - Включите **Force SSL**, **HTTP/2 Support**
4. Нажмите **Save**

#### Vaultwarden

1. **Add Proxy Host**
2. **Details:**
   - **Domain Names:** `vault.example.duckdns.org`
   - **Scheme:** `http`
   - **Forward Hostname/IP:** `vaultwarden`
   - **Forward Port:** `80`
   - Включите **Block Common Exploits** и **Websockets Support**
3. **SSL:** Выберите сертификат, включите **Force SSL**
4. Нажмите **Save**

#### Signoz

1. **Add Proxy Host**
2. **Details:**
   - **Domain Names:** `signoz.example.duckdns.org`
   - **Scheme:** `http`
   - **Forward Hostname/IP:** `signoz`
   - **Forward Port:** `8080`
   - Включите **Block Common Exploits** и **Websockets Support**
3. **SSL:** Выберите сертификат, включите **Force SSL**
4. Нажмите **Save**

## Добавление нового сервиса

1. Добавьте поддомен в Duck DNS
2. Создайте Proxy Host в Nginx Proxy Manager
3. Выберите существующий SSL сертификат (если использовали wildcard)

## Troubleshooting

**DNS Challenge не работает:**
- Проверьте токен Duck DNS
- Убедитесь, что поддомены созданы в Duck DNS
- Проверьте логи: `docker compose logs nginx-proxy-manager`

**Сертификат не обновляется:**
- NPM автоматически обновляет сертификаты за 30 дней до истечения
- Проверьте настройки автоматического обновления в веб-интерфейсе

**502 Bad Gateway:**
- Убедитесь, что сервис запущен: `docker compose ps`
- Проверьте, что Forward Hostname/IP и Port правильные
- Проверьте, что сервис доступен в сети `internal`

## Преимущества

✅ Веб-интерфейс для управления  
✅ Автоматическое обновление сертификатов  
✅ Поддержка множества DNS провайдеров  
✅ Простое добавление новых сервисов
