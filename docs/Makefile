#!/usr/bin/make

DEST=	../build
XSLS?=	xslscript.pl

PACKAGES=	appserve 						\
		appserve-php 						\
		appserve-python appserve-python2.7 appserve-python3.4	\
		appserve-python3.5 appserve-python3.6 appserve-python3.7	\
		appserve-python3.8 appserve-python3.9			\
		appserve-python3.10 appserve-python3.13			\
		appserve-go appserve-go1.7 appserve-go1.8 appserve-go1.9	\
		appserve-go1.10 appserve-go1.12 appserve-go1.13		\
		appserve-ruby

CURDATE:=$(shell date +"%Y-%m-%d")
CURTIME:=$(shell date +"%H:%M:%S %z")


all:		changes changelogs

changes:	$(DEST)/CHANGES

changelogs:	$(addsuffix .rpm-changelog, $(addprefix $(DEST)/, $(PACKAGES))) \
		$(addsuffix .deb-changelog, $(addprefix $(DEST)/, $(PACKAGES)))

$(DEST)/CHANGES:		changes.dtd				\
				changes.xml				\
				change_log_conf.xml			\
				changes.xslt

	mkdir -p $(DEST)

	xmllint --noout --valid changes.xml
	xsltproc --stringparam format generic				\
		--stringparam curdate '$(CURDATE)'			\
		--stringparam curtime '$(CURTIME)'			\
		-o $@ changes.xslt changes.xml

$(DEST)/%.rpm-changelog:	changes.dtd 				\
				changes.xml 				\
				change_log_conf.xml 			\
				changes.xslt
	mkdir -p $(DEST)
	xmllint --noout --valid changes.xml
	xsltproc --stringparam pkgname $* --stringparam format rpm	\
		--stringparam curdate '$(CURDATE)'			\
		--stringparam curtime '$(CURTIME)'			\
		-o $@ changes.xslt changes.xml

$(DEST)/%.deb-changelog:	changes.dtd 				\
				changes.xml 				\
				change_log_conf.xml 			\
				changes.xslt
	mkdir -p $(DEST)
	xmllint --noout --valid changes.xml
	xsltproc --stringparam pkgname $* --stringparam format deb	\
		--stringparam curdate '$(CURDATE)'			\
		--stringparam curtime '$(CURTIME)'			\
		-o $@ changes.xslt changes.xml

changes.xslt:	changes.xsls
	$(XSLS) -o $@ $<

clean:
	rm -rf $(DEST)
