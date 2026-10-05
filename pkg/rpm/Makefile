#!/usr/bin/make

include ../../version

DEFAULT_VERSION := $(NXT_VERSION)
DEFAULT_RELEASE := 1

VERSION ?= $(DEFAULT_VERSION)
RELEASE ?= $(DEFAULT_RELEASE)

PACKAGE_VENDOR = Zhidao HONG <hongzhidao@gmail.com>

ifeq ($(shell test `rpm --eval '0%{?rhel} -eq 6 -a 0%{?amzn} -eq 0'`; echo $$?), 0)
OSVER = centos6
else ifeq ($(shell test `rpm --eval '0%{?rhel} -eq 7 -a 0%{?amzn} -eq 0'`; echo $$?), 0)
OSVER = centos7
else ifeq ($(shell rpm --eval "%{?rhel}"), 8)
OSVER = centos8
else ifeq ($(shell rpm --eval "%{?amzn}"), 1)
OSVER = amazonlinux1
else ifeq ($(shell rpm --eval "%{?amzn}"), 2)
OSVER = amazonlinux2
else ifeq ($(shell test `rpm --eval '0%{?fedora} -eq 41'`; echo $$?),0)
OSVER = fedora41
else ifeq ($(shell test `rpm --eval '0%{?suse_version} -ge 1315 -a 0%{?suse_version} -lt 1330 -a 0%{?is_opensuse} -eq 1'`; echo $$?), 0)
OSVER = opensuse-leap
else ifeq ($(shell test `rpm --eval '0%{?suse_version} -ge 1330 -a 0%{?is_opensuse} -eq 1'`; echo $$?), 0)
OSVER = opensuse-tumbleweed
else ifeq ($(shell test `rpm --eval '0%{?suse_version} -ge 1315 -a 0%{?is_opensuse} -eq 0'`; echo $$?), 0)
OSVER = sles
else ifeq ($(shell test `rpm --eval '0%{?fedora} -ge 26'`; echo $$?),0)
OSVER = fedora
endif

BUILD_DEPENDS_unit = gcc rpm-build rpmlint

ifeq ($(OSVER), centos7)
BUILD_DEPENDS_unit += which
endif

ifeq ($(OSVER), amazonlinux1)
BUILD_DEPENDS_unit += system-rpm-config
endif

ifneq (,$(findstring $(OSVER),opensuse-leap opensuse-tumbleweed sles))
BUILD_DEPENDS_unit += libxml2-tools libxslt1
else
BUILD_DEPENDS_unit += libxml2 libxslt
endif

BUILD_DEPENDS = $(BUILD_DEPENDS_unit)

MODULES=

ifeq ($(OSVER), centos6)
include Makefile.php
include Makefile.python
include Makefile.go
endif

ifeq ($(OSVER), centos7)
include Makefile.php
include Makefile.python27
include Makefile.python36
include Makefile.go
endif

ifeq ($(OSVER), centos8)
include Makefile.php
include Makefile.python27
include Makefile.python36
include Makefile.go
endif

ifeq ($(OSVER), amazonlinux1)
include Makefile.php
include Makefile.python27
include Makefile.python34
include Makefile.python35
include Makefile.python36
include Makefile.go
endif

ifeq ($(OSVER), amazonlinux2)
include Makefile.php
include Makefile.python27
include Makefile.python37
include Makefile.go
endif

ifeq ($(OSVER), opensuse-leap)
include Makefile.python27
include Makefile.python34
include Makefile.go
include Makefile.ruby
endif

ifeq ($(OSVER), opensuse-tumbleweed)
include Makefile.php
include Makefile.python27
include Makefile.python36
include Makefile.go
include Makefile.ruby
endif

ifeq ($(OSVER), sles)
include Makefile.python27
include Makefile.python34
endif

ifeq ($(OSVER), fedora)
include Makefile.php
ifeq ($(shell test `rpm --eval '0%{?fedora} -lt 32'`; echo $$?),0)
include Makefile.python27
endif
ifeq ($(shell test `rpm --eval '0%{?fedora} -ge 35'`; echo $$?),0)
include Makefile.python310
else ifeq ($(shell test `rpm --eval '0%{?fedora} -ge 33'`; echo $$?),0)
include Makefile.python39
else ifeq ($(shell test `rpm --eval '0%{?fedora} -ge 32'`; echo $$?),0)
include Makefile.python38
else ifeq ($(shell test `rpm --eval '0%{?fedora} -ge 29'`; echo $$?),0)
include Makefile.python37
else
include Makefile.python36
endif
include Makefile.go
include Makefile.ruby
endif

ifeq ($(OSVER), fedora41)
include Makefile.php
include Makefile.python313
include Makefile.go
endif

CONFIGURE_ARGS_COMMON=\
	--prefix=/usr \
	--state=%{_sharedstatedir}/appserve \
	--control="unix:/var/run/appserve/control.sock" \
	--pid=/var/run/appserve/appserve.pid \
	--log=/var/log/appserve/appserve.log \
	--tmp=/var/tmp \
	--user=appserve \
	--group=appserve \
	--tests

CONFIGURE_ARGS=$(CONFIGURE_ARGS_COMMON)

export CR=\\n

default:
	@echo "valid targets: all modules appserve $(addprefix appserve-, $(MODULES)) rpmlint specs test test-debug clean"

all: check-build-depends-all appserve modules

modules: $(addprefix appserve-, $(MODULES))

specs: rpmbuild/SPECS/appserve.spec $(addsuffix .spec, $(addprefix rpmbuild/SPECS/appserve-, $(MODULES)))

check-build-depends-%:
	@{ \
	case "$*" in \
		all) pkgs="$(BUILD_DEPENDS)" ;; \
		appserve) pkgs="$(BUILD_DEPENDS_unit)" ;; \
		*) pkgs="$(BUILD_DEPENDS_unit) $(BUILD_DEPENDS_$*)" ;; \
	esac ; \
	not_installed= ; \
	for pkg in $${pkgs}; do \
		rpm -qi --whatprovides $${pkg} >/dev/null 2>&1 ; \
		if [ $$? -ne 0 ]; then \
			not_installed="$${not_installed} $${pkg}" ; \
		fi ; \
	done ; \
	if test -n "$${not_installed}" ; then \
		echo "" >&2 ; \
		echo "The following packages are required in order to proceed:" >&2 ; \
		echo "" >&2 ; \
		echo $${not_installed} >&2 ; \
		echo "" >&2 ; \
		exit 1 ; \
	fi \
	}
	touch $@

rpmbuild/SPECS:
	mkdir -p rpmbuild/SPECS

rpmbuild/SPECS/appserve.spec: appserve.spec.in ../../docs/changes.xml | rpmbuild/SPECS
	cat appserve.spec.in | \
		sed -e "s#%%VERSION%%#$(VERSION)#g" \
		    -e "s#%%RELEASE%%#$(RELEASE)#g" \
		    -e "s#%%CONFIGURE_ARGS%%#$(CONFIGURE_ARGS)#g" \
		    -e "s#%%PACKAGE_VENDOR%%#$(PACKAGE_VENDOR)#g" \
		> rpmbuild/SPECS/appserve.spec
	cd ../../docs && make ../build/appserve.rpm-changelog
ifneq ($(DEFAULT_VERSION)$(DEFAULT_RELEASE), $(VERSION)$(RELEASE))
	cat ../../build/appserve.rpm-changelog | sed -e \
		"s/> - $(DEFAULT_VERSION)-$(DEFAULT_RELEASE)/> - $(VERSION)-$(RELEASE)/" \
		>> rpmbuild/SPECS/appserve.spec
else
	cat ../../build/appserve.rpm-changelog >> rpmbuild/SPECS/appserve.spec
endif

rpmbuild/SOURCES/appserve-$(VERSION).tar.gz:
	cd ../.. && tar -czf pkg/rpm/rpmbuild/SOURCES/appserve-$(VERSION).tar.gz \
		--transform "s#^#appserve-$(VERSION)/#" \
		LICENSE NOTICE CHANGES README configure auto src test version go docs/man/appserved.8.in docs/migration.md

appserve: check-build-depends-appserve rpmbuild/SPECS/appserve.spec rpmbuild/SOURCES/appserve-$(VERSION).tar.gz
	@echo "===> Building $@ package" ; \
	BUILDROOT=`rpmbuild -bc --short-circuit -D "_topdir \`pwd\`/rpmbuild" -D "__spec_build_pre echo bdir=%{_builddir}; exit 0" rpmbuild/SPECS/appserve.spec | grep ^bdir= | cut -d'=' -f 2` ; \
	rpmbuild -D "_topdir `pwd`/rpmbuild" -ba --noclean rpmbuild/SPECS/appserve.spec && \
	ln -s $$BUILDROOT/$@-$(VERSION)/build $@

rpmlint:
	find rpmbuild/ -name "*.rpm" -print -exec rpmlint {} \;

rpmbuild/SPECS/appserve-%.spec: appserve.module.spec.in ../../docs/changes.xml | rpmbuild/SPECS
	@echo "===> Creating $@"
	@{ \
	set -e ; \
	i=100 ; \
	sources= ; \
	for src in $(MODULE_SOURCES_$*); do \
		s="`printf "Source%d: %s\n" $${i} $${src}`" ; \
		sources="$${sources}\n$${s}" ; \
		i=$$(($${i}+1)) ; \
	done ; \
	pkgname=$(shell echo $@ | cut -d '/' -f 3 | tr '_' '-' | cut -d '.' -f 1) ; \
	definitions=`echo "$$MODULE_DEFINITIONS_$*" | sed -e ':a' -e 'N' -e '$$!ba' -e "s/\n/\$$CR/g"` ; \
	preinstall=`echo "$$MODULE_PREINSTALL_$*" | sed -e ':a' -e 'N' -e '$$!ba' -e "s/\n/\$$CR/g"` ; \
	postinstall=`echo "$$MODULE_POSTINSTALL_$*" | sed -e ':a' -e 'N' -e '$$!ba' -e "s/\n/\$$CR/g"` ; \
	files=`echo "$$MODULE_FILES_$*" | sed -e ':a' -e 'N' -e '$$!ba' -e "s/\n/\$$CR/g"` ; \
	post=`echo "$$MODULE_POST_$*" | sed -e ':a' -e 'N' -e '$$!ba' -e "s/\n/\$$CR/g"` ; \
	cat appserve.module.spec.in | sed \
		-e "s#%%NAME%%#$${pkgname}#g" \
		-e "s#%%SUMMARY%%#$(MODULE_SUMMARY_$*)#g" \
		-e "s#%%VERSION%%#$(MODULE_VERSION_$*)#g" \
		-e "s#%%RELEASE%%#$(MODULE_RELEASE_$*)#g" \
		-e "s#%%UNIT_VERSION%%#$(VERSION)#g" \
		-e "s#%%UNIT_RELEASE%%#$(RELEASE)#g" \
		-e "s#%%PACKAGE_VENDOR%%#$(PACKAGE_VENDOR)#g" \
		-e "s#%%MODULE_SOURCES%%#$${sources}#g" \
		-e "s#%%CONFIGURE_ARGS%%#$(CONFIGURE_ARGS_COMMON)#g" \
		-e "s#%%MODULE_CONFARGS%%#$(MODULE_CONFARGS_$*)#g" \
		-e "s#%%MODULE_MAKEARGS%%#$(MODULE_MAKEARGS_$*)#g" \
		-e "s#%%MODULE_INSTARGS%%#$(MODULE_INSTARGS_$*)#g" \
		-e "s#%%MODULE_DEFINITIONS%%#$${definitions}#g" \
		-e "s#%%MODULE_PREINSTALL%%#$${preinstall}#g" \
		-e "s#%%MODULE_POSTINSTALL%%#$${postinstall}#g" \
		-e "s#%%MODULE_FILES%%#$${files}#g" \
		-e "s#%%MODULE_POST%%#$${post}#g" \
		> $@.tmp ; \
	}
	cd ../../docs && make ../build/appserve-$(MODULE_SUFFIX_$*).rpm-changelog
	cat ../../build/appserve-$(MODULE_SUFFIX_$*).rpm-changelog | sed -e \
		"s/> - $(DEFAULT_VERSION)-$(DEFAULT_RELEASE)/> - $(MODULE_VERSION_$*)-$(MODULE_RELEASE_$*)/" \
		>> $@.tmp
	mv $@.tmp $@ 

appserve-%: check-build-depends-% rpmbuild/SPECS/appserve-%.spec rpmbuild/SOURCES/appserve-$(VERSION).tar.gz
	@echo "===> Building $(subst _,-,$@) package" ; \
	BUILDROOT=`rpmbuild -bc --short-circuit -D "_topdir \`pwd\`/rpmbuild" -D "__spec_build_pre echo bdir=%{_builddir}; exit 0" rpmbuild/SPECS/$@.spec | grep ^bdir= | cut -d'=' -f 2` ; \
	rpmbuild -D "_topdir `pwd`/rpmbuild" -ba --noclean rpmbuild/SPECS/$@.spec && \
	ln -s $$BUILDROOT/$(subst _,-,$@)-$(VERSION)/build $@

test: appserve modules
	@{ \
	BUILDROOT=`rpmbuild -bc --short-circuit -D "_topdir \`pwd\`/rpmbuild" -D "__spec_build_pre echo bdir=%{_builddir}; exit 0" rpmbuild/SPECS/appserve.spec | grep ^bdir= | cut -d'=' -f 2` ; \
	NODEBUGS=`find rpmbuild/BUILD -type d -name "build-nodebug"` ; \
	for so in `find $${NODEBUGS} -type f -name "*.so"`; do \
		soname=`basename $${so}` ; \
		test -h $$BUILDROOT/appserve-$(VERSION)/build-nodebug/$${soname} || \
		ln -fs `pwd`/$${so} $$BUILDROOT/appserve-$(VERSION)/build-nodebug/$${soname} ; \
	done ; \
	( cd $$BUILDROOT/appserve-$(VERSION) && rm -f build && ln -s build-nodebug build && env python3 -m pytest --user=nobody $(PYTEST_ARGS) ) ; \
	}

test-debug: appserve modules
	@{ \
	BUILDROOT=`rpmbuild -bc --short-circuit -D "_topdir \`pwd\`/rpmbuild" -D "__spec_build_pre echo bdir=%{_builddir}; exit 0" rpmbuild/SPECS/appserve.spec | grep ^bdir= | cut -d'=' -f 2` ; \
	DEBUGS=`find rpmbuild/BUILD -type d -name "build-debug"` ; \
	for so in `find $$DEBUGS -type f -name "*.so"`; do \
		soname=`basename $${so}` ; \
		test -h $$BUILDROOT/appserve-$(VERSION)/build-debug/$${soname} || \
		ln -fs `pwd`/$${so} $$BUILDROOT/appserve-$(VERSION)/build-debug/$${soname} ; \
	done ; \
	( cd $$BUILDROOT/appserve-$(VERSION) && rm -f build && ln -s build-debug build && env python3 -m pytest --user=nobody $(PYTEST_ARGS) ) ; \
	}

clean:
	rm -rf rpmbuild/SPECS rpmbuild/BUILD rpmbuild/BUILDROOT rpmbuild/RPMS rpmbuild/SRPMS ../../build
	rm -f rpmbuild/SOURCES/appserve-*.tar.gz check-build-depends-*
	find . -maxdepth 1 -type l -delete

.PHONY: default all modules specs rpmlint test test-debug clean

.SECONDARY: $(addprefix check-build-depends-, $(MODULES))
