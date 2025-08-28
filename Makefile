# -----------------------------------------------------------------------------
# Variables (override on the command line if needed, e.g. `make PORT=9000 api`)
# -----------------------------------------------------------------------------
PYTHON       ?= python3.10
BACKEND_DIR  := backend
FRONTEND_DIR := frontend
REDIS_DIR    ?= $(HOME)/myredis/redis-stable
REDIS_SERVER := $(REDIS_DIR)/src/redis-server
CELERY_APP   := tasks
HOST         ?= 0.0.0.0
PORT         ?= 8000

# Phony targets
.PHONY: help install backend-deps frontend-deps download-weights \
        redis celery-beat celery-worker api frontend \
        start stop clean

# ----------------------------------------------------------------------------- 
# Help
# -----------------------------------------------------------------------------
help:
	@echo "WhiStress Makefile — common commands"
	@echo
	@echo "Targets:"
	@echo "  redis              Run local Redis server"
	@echo "  celery-beat        Start Celery beat scheduler"
	@echo "  celery-worker      Start Celery worker"
	@echo "  api                Start FastAPI via uvicorn"
	@echo "  frontend           Start React dev server"
	@echo "  start              Launch all services (runs each in its own background job)"
	@echo "  stop               Kill all services started by this Makefile"
	@echo "  clean              Placeholder for future cleanup tasks"

# ----------------------------------------------------------------------------- 
# Individual services (run each in its own terminal if you prefer)
# -----------------------------------------------------------------------------
redis:
	$(REDIS_SERVER)

celery-beat:
	cd $(BACKEND_DIR) && celery -A $(CELERY_APP) beat --loglevel=info

celery-worker:
	cd $(BACKEND_DIR) && celery -A $(CELERY_APP) worker --loglevel=info --pool=threads

api:
	cd $(BACKEND_DIR) && uvicorn main:app --host $(HOST) --port $(PORT)

frontend:
	cd $(FRONTEND_DIR) && npm run build
# start/run build

# ----------------------------------------------------------------------------- 
# Convenience shortcuts
# -----------------------------------------------------------------------------
# Launch everything (best run under `GNU parallel` or separate terminals)
start:
	@echo "Starting Redis ..."
	@$(MAKE) redis &
	sleep 2
	@echo "Starting Celery beat ..."
	@$(MAKE) celery-beat &
	@echo "Starting Celery worker ..."
	@$(MAKE) celery-worker &
	@echo "Starting FastAPI ..."
	@$(MAKE) api &
	@echo "Starting React frontend (blocking) ..."
	@$(MAKE) frontend

# Kill background services (best‑effort using pkill)
stop:
	-@pkill -f "$(REDIS_SERVER)"            || true
	-@pkill -f "celery -A $(CELERY_APP) beat"   || true
	-@pkill -f "celery -A $(CELERY_APP) worker" || true
	-@pkill -f "uvicorn main:app"               || true
	-@pkill -f "npm start"                      || true
	@echo "All WhiStress services stopped."

clean:
	@echo "Nothing to clean yet."

