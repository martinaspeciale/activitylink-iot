PORT ?= /dev/cu.usbmodemFA8130D5146E1
RUN_ID ?= demo-esame
ADAPTIVE ?= 1
VENV_PYTHON = $(CURDIR)/.venv/bin/python
TUNSLIP6 = $(CURDIR)/vendor/contiki-ng/tools/serial-io/tunslip6

.PHONY: help ports connect-router status start stop-cloud pause resume dashboard

help:
	@printf '%s\n' \
	  'make ports' \
	  'make connect-router [PORT=/dev/cu.usbmodem...]' \
	  'make status' \
	  'make start [RUN_ID=demo-esame] [ADAPTIVE=1]' \
	  'make stop-cloud' \
	  'make pause' \
	  'make resume' \
	  'make dashboard'

ports:
	@"$(VENV_PYTHON)" -m serial.tools.list_ports -v

connect-router:
	@test -x "$(TUNSLIP6)"
	@sudo "$(TUNSLIP6)" -s "$(PORT)" -B 115200 -t utun10 -v 3 fd00::1/64

status:
	@"$(VENV_PYTHON)" scripts/native_stack.py status

start:
	@"$(VENV_PYTHON)" scripts/native_stack.py start --adaptive "$(ADAPTIVE)" --run-id "$(RUN_ID)"

stop-cloud:
	@"$(VENV_PYTHON)" scripts/native_stack.py stop-cloud

pause:
	@"$(VENV_PYTHON)" scripts/control.py pause --host ::1

resume:
	@"$(VENV_PYTHON)" scripts/control.py resume --host ::1

dashboard:
	@open http://127.0.0.1:3000/d/activitylink
