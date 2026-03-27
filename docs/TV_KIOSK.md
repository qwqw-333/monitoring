# TV Kiosk — техническая документация

## Устройство

| Параметр | Значение |
|----------|----------|
| Модель | KIVI TV |
| ОС | Android 11 |
| RAM | 1.38 GB |
| Чипсет | MediaTek |
| IP | 172.30.1.129 |
| ADB | 172.30.1.129:5555 |

## Приложение: WallPanel

**WallPanel** (`xyz.wallpanel.app`) — open-source kiosk-браузер для дашбордов.

- Dashboard URL: `https://grafana.2dep.duckdns.org/d/adzvr2k/voip-tv?kiosk`
- Пользователь Grafana: `monitoring`
- Сессия сохраняется в cookies WebView

### Открыть настройки WallPanel

Нажать на правый нижний угол экрана (области ~1884,1044), либо через ADB:

```bash
adb -s 172.30.1.129:5555 shell input tap 1884 1044
```

### Запустить WallPanel через ADB

```bash
adb -s 172.30.1.129:5555 shell am start -n xyz.wallpanel.app/.ui.activities.BrowserActivityNative
```

## WallPanel REST API

HTTP API работает когда WallPanel находится в режиме браузера (не в настройках).

**Base URL:** `http://172.30.1.129:2971`

### Получить статус

```bash
curl http://172.30.1.129:2971/api/state
# {"currentUrl":"...","screenOn":true,"camera":false,"brightness":102}
```

### Изменить URL

```bash
curl -X POST http://172.30.1.129:2971/api/command \
  -H 'Content-Type: application/json' \
  -d '{"cmd": "urlchange", "url": "https://grafana.2dep.duckdns.org/..."}'
```

> ⚠️ `urlchange` меняет URL только для текущей сессии. Для постоянного изменения — обновить в настройках WallPanel (Application Settings → Dashboard URL).

### Открыть настройки WallPanel удалённо

```bash
curl -X POST http://172.30.1.129:2971/api/command \
  -H 'Content-Type: application/json' \
  -d '{"settings": true}'
```

### Перезагрузить страницу

```bash
curl -X POST http://172.30.1.129:2971/api/command \
  -H 'Content-Type: application/json' \
  -d '{"cmd": "reload"}'
```

### Включить/выключить экран

```bash
# Выключить
curl -X POST http://172.30.1.129:2971/api/command \
  -H 'Content-Type: application/json' \
  -d '{"cmd": "wake", "state": false}'

# Включить
curl -X POST http://172.30.1.129:2971/api/command \
  -H 'Content-Type: application/json' \
  -d '{"cmd": "wake", "state": true}'
```

## ADB управление

### Подключение

```bash
adb connect 172.30.1.129:5555
adb -s 172.30.1.129:5555 devices
```

### Снять скриншот

```bash
adb -s 172.30.1.129:5555 shell screencap -p /sdcard/screen.png
adb -s 172.30.1.129:5555 pull /sdcard/screen.png /tmp/screen.png
```

### Проверить память

```bash
adb -s 172.30.1.129:5555 shell dumpsys meminfo | head -20
```

### Отключённые приложения

Следующие приложения отключены через `pm disable-user` для экономии RAM:

| Пакет | Причина |
|-------|---------|
| `com.android.vending` | Play Store — ~250MB фоновых процессов |

> Восстановить: `adb shell pm enable com.android.vending`

## Архитектурные решения

### Почему WallPanel, а не FreeKIOS

FreeKIOS имеет встроенный таймер неактивности (`@kiosk_inactivity_return_enabled`), который по умолчанию срабатывает каждые ~10 минут и перезагружает страницу. На TV без пользовательского ввода это вызывало постоянные перезагрузки дашборда.

WallPanel лишён этой проблемы и имеет полноценный REST API для удалённого управления.

### Почему нет grafana-image-renderer

`grafana-image-renderer` (headless Chromium) потреблял 434MB RAM на сервере и предназначен для генерации PNG для алертов/экспорта, но не для TV-дисплея. TV-браузер (WebView) рендерит Grafana напрямую в kiosk-режиме — это официальный подход Grafana для TV-дисплеев.
