.PHONY: help up down restart logs ps status health clean pull update backup restore

# Переменные
COMPOSE_FILE := compose.yaml
COMPOSE := docker compose -f $(COMPOSE_FILE)

# Цвета для вывода
GREEN  := \033[0;32m
YELLOW := \033[0;33m
RED    := \033[0;31m
NC     := \033[0m # No Color

help: ## Показать эту справку
	@echo "$(GREEN)Доступные команды:$(NC)"
	@echo ""
	@echo "$(YELLOW)Управление:$(NC)"
	@echo "  $(YELLOW)up$(NC)              Запустить все сервисы"
	@echo "  $(YELLOW)down$(NC)            Остановить все сервисы"
	@echo "  $(YELLOW)restart$(NC)         Перезапустить все сервисы"
	@echo ""
	@echo "$(YELLOW)Логи:$(NC)"
	@echo "  $(YELLOW)logs$(NC)            Логи всех сервисов"
	@echo "  $(YELLOW)logs-traefik$(NC)    Логи Traefik"
	@echo "  $(YELLOW)logs-signoz$(NC)     Логи SigNoz"
	@echo "  $(YELLOW)logs-clickhouse$(NC) Логи ClickHouse"
	@echo ""
	@echo "$(YELLOW)Статус:$(NC)"
	@echo "  $(YELLOW)ps$(NC)              Статус контейнеров"
	@echo "  $(YELLOW)health$(NC)          Статус healthchecks"
	@echo "  $(YELLOW)stats$(NC)           Статистика ресурсов"
	@echo ""
	@echo "$(YELLOW)Обновление:$(NC)"
	@echo "  $(YELLOW)pull$(NC)            Обновить образы"
	@echo "  $(YELLOW)update$(NC)          Обновить и перезапустить"
	@echo ""
	@echo "$(YELLOW)Резервное копирование:$(NC)"
	@echo "  $(YELLOW)backup$(NC)          Создать резервную копию"
	@echo "  $(YELLOW)restore$(NC)         Восстановить из резервной копии"
	@echo ""
	@echo "$(YELLOW)Утилиты:$(NC)"
	@echo "  $(YELLOW)validate$(NC)        Проверить синтаксис compose.yaml"
	@echo "  $(YELLOW)clean$(NC)           Удалить контейнеры (volumes сохраняются)"
	@echo "  $(YELLOW)clean-all$(NC)       Удалить всё включая volumes $(RED)(ОПАСНО!)$(NC)"
	@echo "  $(YELLOW)shell-<service>$(NC) Shell в контейнере (traefik/clickhouse/signoz)"

up: ## Запустить все сервисы
	@echo "$(GREEN)Запуск всех сервисов...$(NC)"
	$(COMPOSE) up -d
	@echo "$(GREEN)Сервисы запущены!$(NC)"
	@$(MAKE) ps

down: ## Остановить все сервисы
	@echo "$(YELLOW)Остановка всех сервисов...$(NC)"
	$(COMPOSE) down

restart: ## Перезапустить все сервисы
	@echo "$(YELLOW)Перезапуск всех сервисов...$(NC)"
	$(COMPOSE) restart
	@$(MAKE) ps

logs: ## Показать логи всех сервисов
	$(COMPOSE) logs -f

logs-traefik: ## Показать логи Traefik
	$(COMPOSE) logs -f traefik

logs-signoz: ## Показать логи SigNoz
	$(COMPOSE) logs -f signoz

logs-clickhouse: ## Показать логи ClickHouse
	$(COMPOSE) logs -f clickhouse

ps: ## Показать статус всех контейнеров
	@echo "$(GREEN)Статус контейнеров:$(NC)"
	$(COMPOSE) ps

status: ps ## Алиас для ps

health: ## Показать статус healthchecks
	@echo "$(GREEN)Статус healthchecks:$(NC)"
	@docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(NAMES|traefik|coredns|uptime-kuma|vaultwarden|clickhouse|zookeeper|signoz|signoz-otel-collector)"

pull: ## Обновить образы Docker
	@echo "$(GREEN)Обновление образов...$(NC)"
	$(COMPOSE) pull

update: pull up ## Обновить образы и перезапустить сервисы
	@echo "$(GREEN)Обновление завершено!$(NC)"

clean: ## Остановить и удалить контейнеры, сети (volumes сохраняются)
	@echo "$(RED)ВНИМАНИЕ: Это удалит контейнеры и сети, но сохранит volumes!$(NC)"
	@read -p "Продолжить? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(COMPOSE) down; \
		echo "$(GREEN)Очистка завершена$(NC)"; \
	fi

clean-all: ## Остановить и удалить контейнеры, сети И volumes (ОПАСНО!)
	@echo "$(RED)ВНИМАНИЕ: Это удалит ВСЕ данные включая volumes!$(NC)"
	@read -p "Вы уверены? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(COMPOSE) down -v; \
		echo "$(GREEN)Полная очистка завершена$(NC)"; \
	fi

backup: ## Создать резервную копию volumes
	@echo "$(GREEN)Создание резервной копии...$(NC)"
	@mkdir -p backups
	@docker run --rm \
		-v $$(pwd)/backups:/backup \
		-v monitoring_uptime-kuma:/data:ro \
		-v monitoring_vaultwarden:/data2:ro \
		-v monitoring_clickhouse-data:/data3:ro \
		-v monitoring_signoz-data:/data4:ro \
		-v monitoring_zookeeper-data:/data5:ro \
		alpine:latest \
		sh -c "tar czf /backup/backup-$$(date +%Y%m%d-%H%M%S).tar.gz -C / data data2 data3 data4 data5 2>/dev/null || true"
	@echo "$(GREEN)Резервная копия создана в директории backups/$(NC)"

restore: ## Восстановить из резервной копии (использование: make restore BACKUP=backups/backup-YYYYMMDD-HHMMSS.tar.gz)
	@if [ -z "$(BACKUP)" ]; then \
		echo "$(RED)Ошибка: укажите файл резервной копии$(NC)"; \
		echo "Использование: make restore BACKUP=backups/backup-YYYYMMDD-HHMMSS.tar.gz"; \
		exit 1; \
	fi
	@if [ ! -f "$(BACKUP)" ]; then \
		echo "$(RED)Ошибка: файл $(BACKUP) не найден$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Восстановление из $(BACKUP)...$(NC)"
	@echo "$(RED)ВНИМАНИЕ: Это перезапишет существующие данные!$(NC)"
	@read -p "Продолжить? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker run --rm \
			-v $$(pwd)/$(BACKUP):/backup.tar.gz:ro \
			-v monitoring_uptime-kuma:/data \
			-v monitoring_vaultwarden:/data2 \
			-v monitoring_clickhouse-data:/data3 \
			-v monitoring_signoz-data:/data4 \
			-v monitoring_zookeeper-data:/data5 \
			alpine:latest \
			sh -c "cd / && tar xzf /backup.tar.gz"; \
		echo "$(GREEN)Восстановление завершено! Перезапустите сервисы: make restart$(NC)"; \
	fi

shell-traefik: ## Открыть shell в контейнере Traefik
	$(COMPOSE) exec traefik sh

shell-clickhouse: ## Открыть shell в контейнере ClickHouse
	$(COMPOSE) exec clickhouse bash

shell-signoz: ## Открыть shell в контейнере SigNoz
	$(COMPOSE) exec signoz sh

validate: ## Проверить синтаксис compose.yaml
	@echo "$(GREEN)Проверка синтаксиса compose.yaml...$(NC)"
	$(COMPOSE) config > /dev/null
	@echo "$(GREEN)Синтаксис корректен!$(NC)"

stats: ## Показать статистику использования ресурсов
	@echo "$(GREEN)Статистика использования ресурсов:$(NC)"
	@docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

