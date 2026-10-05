MODULES+=		php
MODULE_SUFFIX_php=	php

MODULE_SUMMARY_php=	PHP module for AppServe

MODULE_VERSION_php=	$(VERSION)
MODULE_RELEASE_php=	1

MODULE_CONFARGS_php=	php
MODULE_MAKEARGS_php=	php
MODULE_INSTARGS_php=	php-install

MODULE_SOURCES_php=	unit.example-php-app \
			unit.example-php-config

ifeq ($(OSVER), opensuse-tumbleweed)
BUILD_DEPENDS_php=	php7-devel php7-embed
else
BUILD_DEPENDS_php=	php-devel php-embedded
endif

BUILD_DEPENDS+=		$(BUILD_DEPENDS_php)

define MODULE_PREINSTALL_php
%{__mkdir} -p %{buildroot}%{_datadir}/doc/appserve-php/examples/phpinfo-app
%{__install} -m 644 -p %{SOURCE100} \
    %{buildroot}%{_datadir}/doc/appserve-php/examples/phpinfo-app/index.php
%{__install} -m 644 -p %{SOURCE101} \
    %{buildroot}%{_datadir}/doc/appserve-php/examples/appserve.config
endef
export MODULE_PREINSTALL_php

define MODULE_FILES_php
%{_libdir}/appserve/modules/*
%{_libdir}/appserve/debug-modules/*
endef
export MODULE_FILES_php

define MODULE_POST_php
cat <<BANNER
----------------------------------------------------------------------

The $(MODULE_SUMMARY_php) has been installed.

To check out the sample app, run these commands:

 sudo service appserve start
 cd /usr/share/doc/%{name}/examples
 sudo curl -X PUT --data-binary @appserve.config --unix-socket /var/run/appserve/control.sock http://localhost/config
 curl http://localhost:8300/

Project repository (currently private): https://github.com/hongzhidao/AppServe

----------------------------------------------------------------------
BANNER
endef
export MODULE_POST_php
