PORT ?= /dev/cu.usbmodemFA8130D5146E1
TUNSLIP6 = $(CURDIR)/vendor/contiki-ng/tools/serial-io/tunslip6

.PHONY: help connect-router

help:
	@printf '%s\n' 'make connect-router [PORT=/dev/cu.usbmodem...]'

connect-router:
	test -x "$(TUNSLIP6)"
	sudo "$(TUNSLIP6)" -s "$(PORT)" -B 115200 -t utun10 -v 3 fd00::1/64
