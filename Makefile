.PHONY: help up down restart logs ps status health clean pull update validate stats

# Переменные
COMPOSE_FILE := compose.yaml
COMPOSE := docker compose -f $(COMPOSE_FILE)

# Получаем имя сервиса из аргументов командной строки
SERVICE_NAME := $(word 2, $(MAKECMDGOALS))

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
	@echo "  $(YELLOW)up <service>$(NC)    Запустить конкретный сервис (например: make up traefik)"
	@echo "  $(YELLOW)down$(NC)            Остановить все сервисы"
	@echo "  $(YELLOW)down <service>$(NC)   Остановить конкретный сервис (например: make down traefik)"
	@echo "  $(YELLOW)restart$(NC)         Перезапустить все сервисы"
	@echo "  $(YELLOW)restart <service>$(NC) Перезапустить конкретный сервис (например: make restart traefik)"
	@echo ""
	@echo "$(YELLOW)Логи:$(NC)"
	@echo "  $(YELLOW)logs$(NC)            Логи всех сервисов"
	@echo "  $(YELLOW)logs <service>$(NC)   Логи конкретного сервиса (например: make logs traefik)"
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
	@echo "$(YELLOW)Утилиты:$(NC)"
	@echo "  $(YELLOW)validate$(NC)        Проверить синтаксис compose.yaml"
	@echo "  $(YELLOW)clean$(NC)           Удалить контейнеры (volumes сохраняются)"
	@echo "  $(YELLOW)clean-all$(NC)       Удалить всё включая volumes $(RED)(ОПАСНО!)$(NC)"

up: ## Запустить все сервисы или конкретный сервис (make up traefik)
	@if [ -z "$(SERVICE_NAME)" ]; then \
		echo "$(GREEN)Запуск всех сервисов...$(NC)"; \
		$(COMPOSE) up -d; \
		echo "$(GREEN)Сервисы запущены!$(NC)"; \
		$(MAKE) ps; \
	else \
		echo "$(GREEN)Запуск сервиса $(SERVICE_NAME)...$(NC)"; \
		$(COMPOSE) up -d $(SERVICE_NAME); \
		echo "$(GREEN)Сервис $(SERVICE_NAME) запущен!$(NC)"; \
		$(MAKE) ps; \
	fi

down: ## Остановить все сервисы или конкретный сервис (make down traefik)
	@if [ -z "$(SERVICE_NAME)" ]; then \
		echo "$(YELLOW)Остановка всех сервисов...$(NC)"; \
		$(COMPOSE) down; \
	else \
		echo "$(YELLOW)Остановка сервиса $(SERVICE_NAME)...$(NC)"; \
		$(COMPOSE) stop $(SERVICE_NAME); \
		echo "$(GREEN)Сервис $(SERVICE_NAME) остановлен!$(NC)"; \
	fi

restart: ## Перезапустить все сервисы или конкретный сервис (make restart traefik)
	@if [ -z "$(SERVICE_NAME)" ]; then \
		echo "$(YELLOW)Перезапуск всех сервисов...$(NC)"; \
		$(COMPOSE) restart; \
		$(MAKE) ps; \
	else \
		echo "$(YELLOW)Перезапуск сервиса $(SERVICE_NAME)...$(NC)"; \
		$(COMPOSE) restart $(SERVICE_NAME); \
		echo "$(GREEN)Сервис $(SERVICE_NAME) перезапущен!$(NC)"; \
		$(MAKE) ps; \
	fi

logs: ## Показать логи всех сервисов или конкретного сервиса (make logs traefik)
	@if [ -z "$(SERVICE_NAME)" ]; then \
		$(COMPOSE) logs -f; \
	else \
		$(COMPOSE) logs -f $(SERVICE_NAME); \
	fi

ps: ## Показать статус всех контейнеров
	@echo "$(GREEN)Статус контейнеров:$(NC)"
	$(COMPOSE) ps

status: ps ## Алиас для ps

health: ## Показать статус healthchecks
	@echo "$(GREEN)Статус healthchecks:$(NC)"
	@docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(NAMES|traefik|coredns|uptime-kuma|vaultwarden|prometheus|grafana|loki|node-exporter|snmp-exporter|cadvisor)"

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

validate: ## Проверить синтаксис compose.yaml
	@echo "$(GREEN)Проверка синтаксиса compose.yaml...$(NC)"
	$(COMPOSE) config > /dev/null
	@echo "$(GREEN)Синтаксис корректен!$(NC)"

stats: ## Показать статистику использования ресурсов
	@echo "$(GREEN)Статистика использования ресурсов:$(NC)"
	@docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

# Перехватываем аргументы, которые не являются реальными целями
%:
	@:

