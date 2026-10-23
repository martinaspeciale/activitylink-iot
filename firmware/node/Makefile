CONTIKI_PROJECT = activitylink
all: $(CONTIKI_PROJECT)
CONTIKI ?= ../../vendor/contiki-ng
ROLE ?= 1
CFLAGS += -DNODE_ROLE=$(ROLE)
include $(CONTIKI)/Makefile.dir-variables
MODULES += $(CONTIKI_NG_APP_LAYER_DIR)/mqtt
include $(CONTIKI)/Makefile.include
