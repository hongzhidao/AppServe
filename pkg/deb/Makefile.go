MODULES+=		go
MODULE_SUFFIX_go=	go

MODULE_SUMMARY_go=	Go module for AppServe

MODULE_VERSION_go=	$(VERSION)
MODULE_RELEASE_go=	1

MODULE_CONFARGS_go=	go --go-path=/usr/share/gocode
MODULE_MAKEARGS_go=	go
MODULE_INSTARGS_go=	go-install-src

MODULE_SOURCES_go=	unit.example-go-app \
			unit.example-go-config

BUILD_DEPENDS_go=	golang
BUILD_DEPENDS+=		$(BUILD_DEPENDS_go)

MODULE_BUILD_DEPENDS_go=,golang
MODULE_DEPENDS_go=,golang,appserve-dev (= $(VERSION)-$(RELEASE)~$(CODENAME))

MODULE_NOARCH_go=	true

define MODULE_PREINSTALL_go
	mkdir -p debian/appserve-go/usr/share/doc/appserve-go/examples/go-app
	install -m 644 -p debian/unit.example-go-app debian/appserve-go/usr/share/doc/appserve-go/examples/go-app/let-my-people.go
	install -m 644 -p debian/unit.example-go-config debian/appserve-go/usr/share/doc/appserve-go/examples/appserve.config
endef
export MODULE_PREINSTALL_go

define MODULE_POST_go
cat <<BANNER
----------------------------------------------------------------------

The $(MODULE_SUMMARY_go) has been installed.

To check out the sample app, run these commands:

 GOPATH=/usr/share/gocode go build -o /tmp/go-app /usr/share/doc/appserve-$(MODULE_SUFFIX_go)/examples/go-app/let-my-people.go
 sudo service appserve restart
 cd /usr/share/doc/appserve-$(MODULE_SUFFIX_go)/examples
 sudo curl -X PUT --data-binary @appserve.config --unix-socket /var/run/control.appserve.sock http://localhost/config
 curl http://localhost:8500/

Project repository: https://github.com/hongzhidao/AppServe

----------------------------------------------------------------------
BANNER
endef
export MODULE_POST_go
