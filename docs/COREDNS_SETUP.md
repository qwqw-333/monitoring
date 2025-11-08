# Настройка CoreDNS

CoreDNS работает как локальный DNS сервер для резолвинга доменов в закрытом окружении.

## Назначение

- Резолвинг Duck DNS доменов на локальный IP сервера
- Работа в закрытой сети без доступа к публичному DNS
- Централизованное управление DNS записями
- Перенаправление зон на другие DNS серверы (например, PowerDNS)

## Конфигурация

Файл `Corefile` генерируется автоматически из шаблона `coredns/Corefile.template` с использованием переменной окружения `DOMAIN` из файла `.env`. 

По умолчанию используется домен `example.duckdns.org`, но вы можете изменить его, установив переменную `DOMAIN` в файле `.env`:

```bash
DOMAIN=your-domain.duckdns.org
```

Файл `Corefile` настроен для резолвинга доменов `*.${DOMAIN}` на IP адрес сервера.

### Локальное использование (одна машина)

По умолчанию домены резолвятся на `127.0.0.1`:

```
127.0.0.1 kuma.example.duckdns.org
127.0.0.1 vault.example.duckdns.org
127.0.0.1 signoz.example.duckdns.org
```

### Использование в сети

Замените `127.0.0.1` на IP адрес вашего сервера в `Corefile`:

```
YOUR_SERVER_IP kuma.example.duckdns.org
YOUR_SERVER_IP vault.example.duckdns.org
YOUR_SERVER_IP signoz.example.duckdns.org
```

**Как узнать IP адрес:**
```bash
hostname -I | awk '{print $1}'  # Linux
ipconfig getifaddr en0          # macOS
```

## Перенаправление зон на другие DNS серверы

### Пример: перенаправление зоны `.unet` на PowerDNS

Если у вас есть PowerDNS сервер с IP `10.0.0.10`, обслуживающий домен `unet`, добавьте в `Corefile`:

```
# Перенаправление зоны .unet на PowerDNS сервер
unet {
    forward . 10.0.0.10
    log
    errors
}
```

**Важно:**
- Блок должен быть размещен **перед** блоком `.` (catch-all)
- Если PowerDNS слушает на нестандартном порту, укажите: `forward . 10.0.0.10:PORT`
- Для принудительного использования TCP: `forward . 10.0.0.10 { force_tcp }`

**На стороне PowerDNS:**
- Обычно ничего дополнительно настраивать не нужно
- Убедитесь, что PowerDNS принимает запросы на указанном IP и порту

## Настройка клиентских устройств

### macOS

Системные настройки → Сеть → Дополнительно → DNS → Добавьте IP сервера

### Linux

```bash
# Временное решение
echo "nameserver IP_СЕРВЕРА" | sudo tee -a /etc/resolv.conf

# Через NetworkManager
nmcli connection modify "Имя_подключения" ipv4.dns "IP_СЕРВЕРА"
```

### Windows

Панель управления → Сеть → Свойства адаптера → TCP/IPv4 → DNS → Укажите IP сервера

## Проверка работы

```bash
# На сервере
dig @127.0.0.1 kuma.example.duckdns.org

# На клиенте
dig @YOUR_SERVER_IP kuma.example.duckdns.org
```

## Добавление новых доменов

1. Отредактируйте `Corefile`
2. Добавьте запись в секцию `hosts`:
   ```
   YOUR_SERVER_IP newservice.example.duckdns.org
   ```
3. Перезапустите CoreDNS:
   ```bash
   docker compose restart coredns
   ```

## Логирование

```bash
# Просмотр логов
docker compose logs -f coredns
```

## Troubleshooting

**Домены не резолвятся:**
- Проверьте, что CoreDNS запущен: `docker compose ps coredns`
- Проверьте логи: `docker compose logs coredns`
- Убедитесь, что порт 53 не занят: `lsof -i :53`

**Клиенты не могут подключиться:**
- Убедитесь, что в `Corefile` указан правильный IP (не 127.0.0.1)
- Проверьте настройки DNS на клиентах
- Проверьте firewall - порт 53 должен быть открыт
