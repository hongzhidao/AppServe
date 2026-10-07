# AppServe 0.3.0

Release date: October 7, 2026. Git tag: `0.3`.

AppServe 0.3.0 simplifies application workers and expands application-level
observability. Python, PHP, Ruby, Go, and external applications remain supported.

## Changes

- Application request handling uses one thread per worker process. Python and
  Ruby `threads` and `thread_stack_size` configuration and Ruby thread hooks are
  removed. WSGI, Ruby, Go, and external request handlers execute on the worker
  thread; ASGI retains asynchronous concurrency within its event loop.
- Simplified `libunit` and Go request handling, including shared-memory flow
  control and shutdown behavior. The Go binding no longer starts request-handler
  or receiver goroutines.
- Separated application process state from ports and moved router state into
  thread contexts. In-flight HTTP and WebSocket requests retain worker context
  after application removal or worker detachment.
- Configuration API responses include application startup error details.
- Application status reports worker-pool `max`, `spare`, `busy`, `idle`, and
  `crash`; global process status sums `busy`, `idle`, and `crash`. The old
  `running`, `starting`, and connection statistics are removed. `crash` counts
  workers exiting on a signal or with a nonzero exit code; normal recycling,
  application restarts, and prototype exits are excluded.
- Application and global request statistics report `total`, `active`, `queued`,
  `completed`, and `failed`. `queued` is the subset of active requests waiting
  for a worker to acknowledge receipt, including startup and acknowledgement
  delivery time. Completed requests include valid application responses
  regardless of HTTP status and successful WebSocket upgrades; failed requests
  include processing errors, timeouts, and cancellations.
- Response statistics group headers by `1xx` through `5xx`, including AppServe
  error responses after a request enters an application.
- Latency statistics report `sum`, `avg`, `max`, `p95`, and `p99` in integer
  milliseconds, from application queue entry until completion or failure.
  Percentiles are approximate cumulative values from fixed-size latency buckets;
  global percentiles use merged application samples. Fragmented status reports
  support the larger snapshots. WebSocket sessions are timed only until upgrade.
  Statistics are approximate; counters belong to the current application
  configuration instance.
- Corrected thread startup, configuration mapping alignment, MurmurHash2
  shifts, and empty-string formatting.
- Expanded the README with features and quick-start instructions. Removed the
  migration guide and its packaging references; container documentation links
  now point to the README.

Existing configurations using removed application thread options are rejected.
Rebuild language modules and external applications against the deployed version.
Use multiple worker processes for parallel synchronous request handling.

## Verification

Original release verification on Linux aarch64 with GCC 13.3.0,
Python 3.12.3, and Go 1.22.2:

- The daemon, Python module, Go binding, and C test programs built successfully.
- C tests and the UTF-8 filename test passed, including thread startup,
  configuration mapping, MurmurHash2, formatting, and Forwarded parser coverage.
- The full regression suite in default mode passed: **473 passed, 126 skipped**.
  This includes Python/ASGI, WebSocket, Go, configuration, HTTP, Forwarded,
  process management, isolation, status, respawn, and log rotation tests.
  Tests ran in a separate network namespace to avoid occupied host ports.
- Installation and uninstallation passed for the daemon, manpage, Python
  module, `libunit`, headers, and pkg-config file.
- The XML changelog validated and generated text, Debian, and RPM changelogs
  were checked.
- An extracted source distribution built successfully and passed the C tests
  and UTF-8 filename test.

PHP and Ruby modules, Docker images, and Debian/RPM binary packages were not
built as part of this release verification.

Additional verification for the expanded 0.3.0 status features on Linux aarch64
with GCC 13.3.0 and Python 3.12.3:

- The daemon, Python module, and C test programs built successfully with debug
  assertions enabled.
- C tests passed, including latency bucket boundaries, percentile ranks, and
  aggregation; the UTF-8 filename test passed.
- Status, respawn, ASGI application, and ASGI WebSocket regressions passed in
  default mode: **80 passed, 7 skipped**. Tests ran in a separate network
  namespace. Coverage includes queued requests, startup failures, cumulative
  P95/P99 latency, fragmented reports, abnormal worker exits, normal recycling,
  configuration lifetime, timeouts, cancellations, and WebSocket upgrades.
- The XML changelog validated; generated text, Debian, and RPM changelogs were
  checked.

# AppServe 0.2.0

Release date: October 5, 2026.

AppServe 0.2.0 focuses on serving applications behind a front-end proxy.
Listeners pass requests directly to fixed applications and application targets.
Python, PHP, Ruby, Go, and external applications remain supported.

## Changes

- Removed Java/Servlet/JSP, Node.js `unit-http`, and Perl/PSGI support,
  including their packages and container images.
- Removed built-in routing, route actions, configuration variables, NJS
  expressions, and JavaScript module storage and control APIs.
- Removed built-in TLS and certificate management, static file serving,
  reverse proxying, upstream load balancing, and access logging.
- Removed the OpenSSL, PCRE/PCRE2, and NJS dependencies and their configure
  options.
- Added standard HTTP `Forwarded` header processing (RFC 7239). A listener's
  `forwarded.trusted` IP/CIDR rules authorize proxy metadata. Client address
  and scheme come from the same selected chain element; the connection peer
  remains the trust anchor.
- Removed unused job, cache, buffer filter, buffer pool, fiber, memory zone,
  vector, time parsing, and sendfile code. Connection output uses memory
  buffers; large request bodies still use temporary files passed to applications.

## Verification

Verified on Linux aarch64 with GCC 13.3.0 and Python 3.12.3:

- The daemon, Python module, and C test programs built successfully.
- C tests, including the Forwarded parser tests, and the UTF-8 filename
  test passed.
- Configuration, HTTP, Forwarded, Python/ASGI, application targets,
  environment, process management, status, log rotation, and respawn
  regressions passed in the default test mode: **369 passed, 16 skipped**,
  including an isolated rerun of the status tests after a transient
  connection-counter assertion.
- Staged installation and uninstallation passed for the daemon, manpage,
  Python module, `libunit`, headers, and pkg-config file.
- The AppServe XML changelog validated, and generated text and package
  changelogs were checked.
- The source distribution was extracted and built successfully, C tests
  passed, and its SHA-512 checksum was verified.

PHP, Ruby, and Go were not runtime-tested for this release. Docker images
and Debian/RPM binary packages were not built.

## Known issues

The inherited `--restart`-mode shutdown alert in
`test_python_restart_longstart` and intermittent listener port-release
regression reported for 0.1.0 have not been addressed by this release.

`test_status_fixed_application` can read connection counters before the
asynchronous connection close is reflected. It failed once during this
release's full regression run; all five status tests passed when rerun
in isolation.

# AppServe 0.1.0

Release date: October 5, 2026.

This is the first release under the AppServe name, continuing the development
and maintenance of NGINX Unit. The project repository is at
https://github.com/hongzhidao/AppServe.

## Changes

- The daemon is now `appserved`, with `appserved-debug` for debug packages.
- Packages and services use `appserve` names, along with their default state,
  module, PID, log, and control socket paths.
- Version output, logs, process titles, and HTTP `Server` headers identify
  AppServe.
- Docker images build from local source rather than fetching upstream Unit.
- The configuration API, `libunit`, and existing language binding identifiers
  retain their names for application source compatibility.

Original copyright notices are retained.

## Verification

Verified on Linux aarch64 with GCC 13.3.0, Python 3.12.3, and OpenSSL 3.0.13:

- The daemon, Python module, and C test programs built successfully.
- C tests passed.
- Selected configuration, HTTP, static file, logging, Python/ASGI, process
  management, and respawn regressions passed in the default test mode:
  **171 passed, 16 skipped**.
- Staged installation and uninstallation passed for the daemon, manpage,
  Python module, `libunit`, headers, and pkg-config file.
- Changelog generation, package example configuration, module source
  references, and generated Dockerfile syntax were checked.

Docker images and Debian/RPM binary packages have not been built as part of
this release verification. Other language bindings were not runtime-tested.

## Known issues

In the test suite's `--restart` mode, `test_python_restart_longstart` can emit
`too many port socket messages` during shutdown. This alert was reproduced
with the same toolchain on the pre-branding commit `700a900e`; it remains an
unresolved inherited issue. The test passes in the default mode.

The listener port-release regression also failed intermittently during the
`--restart` run and passed when rerun in isolation. The final default-mode
regression run passed.
