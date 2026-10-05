# Migrating from NGINX Unit to AppServe

AppServe continues NGINX Unit with an independent product name. The project
repository is https://github.com/hongzhidao/AppServe and is currently private.
Repository access is required for source code and issue tracking.

## Executables and services

| Unit | AppServe |
| --- | --- |
| `unitd` | `appserved` |
| `unitd-debug` | `appserved-debug` |
| `unit.service` | `appserve.service` |
| `unit-debug.service` | `appserve-debug.service` |
| `unit` Debian/RPM package | `appserve` |
| `unit-*` Debian/RPM module packages | `appserve-*` |
| `unit-dev` / `unit-devel` | `appserve-dev` / `appserve-devel` |

Update deployment scripts, service commands, monitoring, and container commands
to use these names. Process titles start with `appserve:` and HTTP responses
identify the server as `AppServe/<version>`.

## Default paths

Source builds keep their configurable directory layout. The default PID, log,
and control socket filenames become `appserve.pid`, `appserve.log`, and
`control.appserve.sock`. All paths can still be overridden using configure
options or daemon command-line options.

Debian packages and Docker images use:

- State: `/var/lib/appserve`
- Modules: `/usr/lib/appserve/modules` (debug: `debug-modules`)
- Control socket: `/var/run/control.appserve.sock`
- PID: `/var/run/appserve.pid`
- Log: `/var/log/appserve.log`

RPM packages use the distribution's library and shared-state directories with
the `appserve` subdirectory, `/var/run/appserve/control.sock`,
`/var/run/appserve/appserve.pid`, and `/var/log/appserve/appserve.log`.
Packages and images use the `appserve` user and group for non-privileged
processes. Check application, document-root, and socket permissions accordingly.

Before switching services, stop Unit and back up its state directory, including
configuration, certificates, and JavaScript modules. Copy that state into the
AppServe state directory, preserving permissions, or explicitly configure
AppServe to use the existing directory. Start AppServe only after Unit has
stopped if both instances use the same state or listener addresses. Package
installation does not automatically migrate existing state or service settings.

## Application compatibility

The configuration API, `libunit.a`, `unit.pc`, `nxt_unit_*` C API, and
`*.unit.so` language module filenames retain their existing names. The Go
import path `unit.nginx.org/go`, PHP SAPI name `unit`, and Ruby binding
namespace are also retained. Keeping these identifiers avoids requiring
application source changes. Rebuild language modules and external applications
against the AppServe version being deployed; retaining API names does not
guarantee binary compatibility between different versions or builds.

Java application support is removed starting with AppServe 0.2.0. The Java
module, Servlet/JSP container, and `appserve-jsc*` packages are no longer
provided. Existing applications configured with `"type": "java"`, including
version-qualified types, must be removed from the configuration before upgrading.

Node.js application support is removed starting with AppServe 0.2.0. The
`unit-http` package, HTTP/WebSocket bindings, module loaders, and Node.js
container images are no longer provided. Existing `external` applications
that depend on `unit-http` must be migrated before upgrading.

Perl/PSGI application support is removed starting with AppServe 0.2.0. The
Perl module, `appserve-perl` packages, and Perl container images are no longer
provided. Existing applications configured with `"type": "perl"`, including
version-qualified types, must be removed from the configuration before upgrading.

## Routing compatibility

The route action's `rewrite` option is removed starting with AppServe 0.2.0.
Remove it from route actions and nested fallback actions before upgrading.
Configurations containing this option are rejected as having an unknown
parameter. Requests keep their original target throughout routing.

The route action's `response_headers` option is also removed starting with
AppServe 0.2.0. Remove it from route actions and nested fallback actions before
upgrading. Configurations containing this option, including an empty object,
are rejected as having an unknown parameter. Configure custom response headers
in the application or front-end proxy instead.

## Static file serving

Built-in static file serving is removed starting with AppServe 0.2.0. Migrate
routes using the `share` action to an application or front-end proxy before
upgrading. The `share` action and its `types`, `chroot`, `follow_symlinks`,
`traverse_mounts`, and `fallback` options are no longer supported. Route actions
now support `pass` or `return`.

Remove `settings/http/static`, including its `mime_types` configuration, before
upgrading. Configurations containing these removed settings are rejected,
including an empty `static` object. File extension mapping, index files,
directory redirects, and static file ETags must be handled by the replacement
file server.

## Reverse proxying

Built-in reverse proxying and upstream load balancing are removed starting
with AppServe 0.2.0. Migrate route actions using `proxy` and listener or route
`pass` values targeting `upstreams/...` to a front-end proxy before upgrading.
Remove the top-level `upstreams` object, including an empty object, from the
configuration. These configurations are rejected; route actions now support
only `pass` to applications or routes and `return`.

## TLS compatibility

Built-in TLS support is removed starting with AppServe 0.2.0. Remove `tls`
objects from listener configurations before upgrading and terminate TLS at a
front-end proxy. TLS backends, certificate management, SNI, and TLS session
settings are no longer provided. The `/certificates` control API is removed,
and AppServe no longer loads certificates from the state directory or uploads
PEM bundles from `/docker-entrypoint.d/`.

Applications can still receive the original HTTPS scheme through a listener's
`forwarded.protocol` setting. Configure its `source` to match the front-end
proxy. Scheme-based routing and application scheme metadata continue to use
this forwarded value.

## Access logging

Built-in access logging is removed starting with AppServe 0.2.0. Remove the
top-level `access_log` setting before upgrading, whether it is a path string
or an object with `path`, `format`, or `if`. Configurations containing this
setting, including an empty object, are rejected as having an unknown
parameter. Record HTTP access logs in the application or front-end proxy.

The access-log response variables `$status`, `$body_bytes_sent`, and
`$response_header_*` are also removed. Request variables remain available in
route conditions and dynamic `pass` values.

Daemon and application diagnostic output still uses `appserve.log`, and
`SIGUSR1` continues to reopen that log for rotation.

## Containers

Generate Dockerfiles with `make -C pkg/docker dockerfiles` and build images with
`make -C pkg/docker build`. Images are built from a local source archive, so
private-repository credentials are not needed inside the Docker build.
Local image tags use `appserve:<version>-<variant>`. The `REGISTRY` make variable
selects the destination for the explicit `tag` and `push` targets.
