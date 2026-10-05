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
import path `unit.nginx.org/go`, Node.js package `unit-http`, PHP SAPI name
`unit`, and Ruby/Perl binding namespaces are also retained. Keeping these
identifiers avoids requiring application source changes. Rebuild language modules
and external applications against the AppServe version being deployed; retaining
API names does not guarantee binary compatibility between different versions or
builds.

Java application support is removed starting with AppServe 0.2.0. The Java
module, Servlet/JSP container, and `appserve-jsc*` packages are no longer
provided. Existing applications configured with `"type": "java"`, including
version-qualified types, must be removed from the configuration before upgrading.

## Containers

Generate Dockerfiles with `make -C pkg/docker dockerfiles` and build images with
`make -C pkg/docker build`. Images are built from a local source archive, so
private-repository credentials are not needed inside the Docker build.
Local image tags use `appserve:<version>-<variant>`. The `REGISTRY` make variable
selects the destination for the explicit `tag` and `push` targets.
