CONTIKI_PROJECT = activitylink
all: $(CONTIKI_PROJECT)
CONTIKI ?= $(if $(wildcard ../../workspace/vendor/contiki-ng),../../workspace/vendor/contiki-ng,../../vendor/contiki-ng)

# Keep local build artifacts outside the presentation tree.
BUILD_DIR ?= $(if $(wildcard ../../workspace/vendor/contiki-ng),../../workspace/runtime/firmware-build,build)

# Build the same source as HAR (1) or feedback (2)
ROLE ?= 1
CFLAGS += -DNODE_ROLE=$(ROLE)
include $(CONTIKI)/Makefile.dir-variables
MODULES += $(CONTIKI_NG_APP_LAYER_DIR)/mqtt
include $(CONTIKI)/Makefile.include
