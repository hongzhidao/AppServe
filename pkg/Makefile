#!/usr/bin/make

include ../version
include shasum.mak

VERSION ?= $(NXT_VERSION)
RELEASE ?= 1

default:
	@echo "available targets: dist rpm deb docker npm"

dist:
	rm -f appserve-$(VERSION).tar.gz
	cd .. && git archive \
		--output pkg/appserve-$(VERSION).tar.gz \
		--prefix appserve-$(VERSION)/ \
		--worktree-attributes \
		$(VERSION) ./
	$(SHA512SUM) appserve-$(VERSION).tar.gz > appserve-$(VERSION).tar.gz.sha512

rpm:
	@cd rpm && VERSION=$(VERSION) RELEASE=$(RELEASE) make all

deb:
	@cd deb && VERSION=$(VERSION) RELEASE=$(RELEASE) make all

docker:
	@cd docker && VERSION=$(VERSION) RELEASE=$(RELEASE) make all

npm:
	@cd npm && VERSION=$(VERSION) RELEASE=$(RELEASE) make all

njs:
	@cd contrib && make .njs

clean:
	@cd rpm && make clean
	@cd deb && make clean
	@cd docker && make clean
	@cd npm && make clean
	@cd contrib && make clean
	rm -f appserve-$(VERSION).tar.gz
	rm -f appserve-$(VERSION).tar.gz.sha512

.PHONY: default rpm deb docker npm clean
