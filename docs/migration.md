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

Built-in request routing is removed starting with AppServe 0.2.0. Remove the
top-level `routes` configuration, including empty arrays and objects, before
upgrading. Listener `pass` values targeting `routes` or `routes/...` are no
longer supported. Route matching, route chains, and route actions, including
`return`, `location`, `rewrite`, and `response_headers`, are removed. Move
request matching, redirects, and custom responses to the application or
front-end proxy.

Listeners pass requests directly to `applications/<name>` or
`applications/<name>/<target>`. The legacy listener `application` setting also
remains supported.

The routing-specific PCRE/PCRE2 dependency and the `--no-regex` and
`--no-pcre2` configure options are removed.

## Variables and JavaScript

Configuration variables and NJS expressions are removed starting with AppServe
0.2.0. Listener `pass` values must name a fixed application and optional target.
Replace `$variable`, `${variable}`, and backtick JavaScript expressions with
`applications/<name>` or `applications/<name>/<target>` before upgrading.
Dynamic application and target selection must be handled by the application
or front-end proxy. Percent-encode special characters in fixed application
and target names.

Remove `settings/js_module` from existing configurations. The `/js_modules`
control API, JavaScript module storage, and the `--njs` configure option are
removed. AppServe no longer creates or loads the state directory's `scripts/`
subdirectory.

## Static file serving

Built-in static file serving is removed starting with AppServe 0.2.0. Migrate
routes using the `share` action to an application or front-end proxy before
upgrading. The `share` action and its `types`, `chroot`, `follow_symlinks`,
`traverse_mounts`, and `fallback` options are no longer supported.

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
configuration. These configurations are rejected.

## TLS compatibility

Built-in TLS support is removed starting with AppServe 0.2.0. Remove `tls`
objects from listener configurations before upgrading and terminate TLS at a
front-end proxy. TLS backends, certificate management, SNI, and TLS session
settings are no longer provided. The `/certificates` control API is removed,
and AppServe no longer loads certificates from the state directory or uploads
PEM bundles from `/docker-entrypoint.d/`.

Applications can still receive the original HTTPS scheme through the standard
`Forwarded` request header and a listener's `forwarded.trusted` setting, as
described below.

## Forwarded request metadata

Starting with AppServe 0.2.0, listener forwarding uses the standard HTTP
`Forwarded` header (RFC 7239). Replace the old listener `client_ip` object and
the old `forwarded` options (`source`, `client_ip`, `protocol`, `recursive`)
with:

```json
{
  "pass": "applications/app",
  "forwarded": {
    "trusted": ["127.0.0.1", "::1", "10.20.0.0/16"]
  }
}
```

`trusted` is required and accepts an IP address or an array of IP addresses
and CIDRs. Ports, ranges, negated patterns and hostnames are not accepted.
An empty array trusts nobody; omitting `forwarded` disables processing.
The original connection peer is always used to authorize header processing.
IPv4-mapped IPv6 peers also match the corresponding IPv4 trust rules.

Configure the front-end proxy to send, for example:

```http
Forwarded: for=203.0.113.9;proto=https
Forwarded: for="[2001:db8::1]:443";proto=https
```

`for` sets the application's client address and `proto` sets its scheme.
Only `http` and `https` are applied, case-insensitively. IPv6 addresses must
be enclosed in brackets and quoted; addresses with ports must also be quoted.
The header and parameter names are case-insensitive. Quoted strings and
escaped characters are supported. Other parameters, including `host` and
`by`, do not change application metadata. The original headers remain
available to applications.

Multiple header fields form one ordered chain. AppServe walks right to left,
skipping trusted proxy addresses and selecting the first untrusted address,
or the leftmost address if all addresses are trusted. The scheme comes only
from that same element; if it is absent or unsupported, the scheme remains
`http`. A missing `for`, `unknown`, or an obfuscated node stops traversal,
preserving the connection peer as the application address and applying only
that element's supported scheme. No older element is consulted.

Malformed quoting anywhere makes the header unusable. Empty or malformed
elements, invalid addresses, or duplicate parameter names in the traversed
part of a chain leave both address and scheme unchanged. Metadata in the
untrusted prefix does not affect the selected result.
Headers exceeding 32,767 elements or parameters per element are ignored.

Old configurations are rejected. `X-Forwarded-For`, `X-Real-IP` and
`X-Forwarded-Proto` no longer change application metadata; migrate the
front-end proxy to emit `Forwarded` before upgrading.

## Access logging

Built-in access logging is removed starting with AppServe 0.2.0. Remove the
top-level `access_log` setting before upgrading, whether it is a path string
or an object with `path`, `format`, or `if`. Configurations containing this
setting, including an empty object, are rejected as having an unknown
parameter. Record HTTP access logs in the application or front-end proxy.

The access-log response variables `$status`, `$body_bytes_sent`, and
`$response_header_*` are also removed.

Daemon and application diagnostic output still uses `appserve.log`, and
`SIGUSR1` continues to reopen that log for rotation.

## Containers

Generate Dockerfiles with `make -C pkg/docker dockerfiles` and build images with
`make -C pkg/docker build`. Images are built from a local source archive, so
private-repository credentials are not needed inside the Docker build.
Local image tags use `appserve:<version>-<variant>`. The `REGISTRY` make variable
selects the destination for the explicit `tag` and `push` targets.
