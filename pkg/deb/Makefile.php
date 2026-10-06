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

ifneq (,$(findstring $(CODENAME),trusty jessie))
BUILD_DEPENDS_php=	php5-dev libphp5-embed
MODULE_BUILD_DEPENDS_php=,php5-dev,libphp5-embed
MODULE_DEPENDS_php=,libphp5-embed
else
BUILD_DEPENDS_php=	php-dev libphp-embed
MODULE_BUILD_DEPENDS_php=,php-dev,libphp-embed
MODULE_DEPENDS_php=,libphp-embed
endif

BUILD_DEPENDS+=		$(BUILD_DEPENDS_php)

define MODULE_PREINSTALL_php
	mkdir -p debian/appserve-php/usr/share/doc/appserve-php/examples/phpinfo-app
	install -m 644 -p debian/unit.example-php-app debian/appserve-php/usr/share/doc/appserve-php/examples/phpinfo-app/index.php
	install -m 644 -p debian/unit.example-php-config debian/appserve-php/usr/share/doc/appserve-php/examples/appserve.config
endef
export MODULE_PREINSTALL_php

define MODULE_POST_php
cat <<BANNER
----------------------------------------------------------------------

The $(MODULE_SUMMARY_php) has been installed.

To check out the sample app, run these commands:

 sudo service appserve restart
 cd /usr/share/doc/appserve-$(MODULE_SUFFIX_php)/examples
 sudo curl -X PUT --data-binary @appserve.config --unix-socket /var/run/control.appserve.sock http://localhost/config
 curl http://localhost:8300/

Project repository: https://github.com/hongzhidao/AppServe

----------------------------------------------------------------------
BANNER
endef
export MODULE_POST_php
