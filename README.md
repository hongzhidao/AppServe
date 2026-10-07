# AppServe

**A multi-language application server with dynamic configuration and
elastic process management.**

AppServe runs applications on UNIX-like systems with a unified HTTP control
API, independently managed worker pools, and application-level runtime
statistics. Configure how applications run, let worker pools adapt to request
demand, and inspect their state while the server is running.

## Core features

### Dynamic configuration

Manage applications and listeners through an HTTP API using JSON:

- Add, update, and remove applications and listening endpoints.
- Read the full configuration or modify individual configuration paths.
- Adjust application environments, entry points, and process-pool policies
  without restarting the server.
- Validate configuration before applying it and save applied configuration
  for subsequent starts.

### Elastic process management

Each application has its own worker pool. Choose a fixed process count or a
pool that adapts to demand:

- Start workers on demand, within a configured maximum.
- Maintain spare workers for incoming requests.
- Reclaim excess idle workers after a configurable timeout.
- Replace workers after abnormal exits when the pool needs more capacity.
- Restart an application independently or recycle workers after a configured
  number of requests.

Dynamic configuration defines the policy; process management maintains the
pool according to that policy as demand changes.

### Multi-language applications

Run applications in different languages with a consistent configuration and
management model:

| Application | Interface |
| --- | --- |
| Python | WSGI and ASGI |
| PHP | PHP SAPI |
| Ruby | Rack |
| Go | Go binding for HTTP handlers |
| External | C application API |

Python and PHP applications can define multiple named application targets.
Each listener selects a fixed application and optional target.

Application workers use one request execution thread, with parallelism
provided by multiple processes. Python WSGI, PHP, Ruby, and Go handlers run
synchronously; Python ASGI applications can handle concurrent requests on
their event loop.

### Application-level observability

Query the `/status` API for server and application runtime statistics:

- Total, active, queued, completed, and failed application requests, per
  application and in total.
- Busy and idle application workers, per application and in total.
- HTTP response counts by status class, per application and in total.
- Application request latency, per application and in total.

Read `/status/applications/<name>/processes` for an application's worker-pool
policy and current state:

```json
{
  "max": 8,
  "spare": 2,
  "busy": 3,
  "idle": 2,
  "crash": 27
}
```

`max` is the configured worker limit, and `spare` is the desired number of
idle workers. A fixed `processes` count sets both to that count. The actual
`idle` count can differ from `spare` while workers start, serve requests, or
await idle-timeout reclamation.

`busy` and `idle` are current worker counts: `busy` is the number of running
workers that are not idle, including workers serving WebSocket sessions.
Their sum estimates the running worker count. Worker counts and active requests
are sampled independently without locking request handling, so they can briefly
differ while workers start, become idle, or exit. `busy` is clamped to zero if
the sampled idle count exceeds the sampled running count.

`crash` is the cumulative number of worker processes in the application's pool
that exited on a signal or with a nonzero exit code. Each worker exit counts
once, regardless of how many requests it interrupted. Normal exits, idle-timeout
reclamation, request-limit recycling, and application restarts do not add to it.
Prototype and server management processes are excluded. Replacing the application's
configuration resets the counter; listener-only changes and worker restarts
preserve it.

`/status/processes` returns `busy`, `idle`, and `crash`, summed across the configured
applications' worker pools shown in the same status response. An application's
previous configuration, or a deleted application, may still have draining
workers; those old pools are outside this response.

`/status/applications/<name>/requests` returns `total`, `active`, `queued`,
`completed`, and `failed`:

- `total` counts requests entering the application's request queue.
- `active` includes queued requests and requests awaiting an application response.
- `queued` counts requests waiting for a worker to acknowledge receipt. It is
  part of `active`, not an additional request count. It includes worker startup
  and acknowledgement delivery time, and drops when receipt is acknowledged or
  the request is removed after cancellation or failure. Acknowledged requests
  are no longer queued, even if application processing has not finished.
- `completed` counts complete, valid application responses, including normal
  HTTP 4xx/5xx responses, and successful WebSocket upgrades.
- `failed` counts requests ending without a complete, valid application response,
  including startup failures, timeouts, worker exits, response errors, and
  cancellations before completion.

A WebSocket upgrade counts once; subsequent frames and session closure do not
count as requests, and an upgraded session is no longer an active request.
Completion describes application processing, not delivery to the client.
Requests rejected before entering an application are not counted. At rest,
`total = active + completed + failed`, and `queued <= active`; independent
samples can briefly differ.

`/status/requests` sums all five fields from the applications in the same
status response. Counters belong to each application configuration instance:
replacing an application's configuration resets its counters, and deleting it
removes its counters from the totals. Listener-only changes and worker restarts
preserve them. Draining requests from old application configurations are excluded.

`/status/applications/<name>/responses` returns `1xx`, `2xx`, `3xx`, `4xx`, and
`5xx` counters. A response counts once when its header is queued for sending,
including errors generated by AppServe after a request enters an application.
Responses rejected before entering an application and nonstandard status codes
outside 100–599 are excluded.

A streaming response retains its status count if it later fails or is cancelled.
A WebSocket upgrade counts once as `1xx`; frames and session closure do not add
responses. These counters describe response headers, not completed delivery.
`/status/responses` sums the application counters in the same status response.
Response counters follow the same configuration lifetime as request counters.
Response counts are approximate under concurrent updates.

`/status/applications/<name>/latency` returns `sum`, `avg`, `max`, `p95`, and
`p99`, all in integer milliseconds. `sum` is the cumulative duration of completed
and failed requests, `avg` is `sum / (requests.completed + requests.failed)`
rounded down, and `max` is the longest duration. All fields are zero before any
request ends.

`p95` and `p99` estimate the 95th and 99th percentiles of completed and failed
request durations using fixed-size latency buckets (about 4 KiB per application).
Buckets record each millisecond below 16 ms and divide each larger power-of-two
range into eight equal-width buckets. Percentiles use the bucket containing
the nearest rank, rounded up, and report its upper bound, capped at `max`.
For example, a 203 ms sample falls in the 192–207 ms bucket. Bucket rounding
can overestimate a percentile by up to about 12.5% before the cap at `max`.
These are cumulative percentiles, not a recent-time window.

Latency starts when a request enters the application queue and ends when its
response completes or its failure is detected. It includes queueing, worker
startup, and application processing, but excludes request upload before entering
the application and response delivery to the client. WebSocket requests are timed
until the upgrade completes; frames and session closure add no samples.

`/status/latency` sums application durations, computes the weighted average using
the global completed and failed request counts, and takes the largest application
maximum. Global `p95` and `p99` are calculated from the merged application
latency buckets, rather than averaging application percentiles. Percentile ranks
use the sample count in the bucket snapshot, which can differ from independently
sampled request counters. Latency recording and sampling add no locks or atomic
operations; concurrent updates can be lost and snapshots can briefly differ.
Latency statistics are approximate and follow the request counters' configuration
lifetime.

Richer application-level statistics are a focus of ongoing development,
supporting performance analysis, troubleshooting, and capacity planning.

### Execution environments and isolation

Configure each application's user, group, environment variables, and working
directory. Set application response timeouts, worker request limits, and
shared-memory limits. On supported platforms, use root filesystems and
namespaces to isolate application environments.

### HTTP and WebSocket application serving

AppServe handles HTTP requests, WebSocket connections, request-body buffering,
and temporary-file storage for large request bodies. Read, write, and idle
timeouts are configurable.

When deployed behind a trusted proxy, standard `Forwarded` header processing
preserves the original client address and HTTP scheme for applications.

## Deployment model

AppServe focuses on application execution and runtime management. Deploy it
behind a front-end proxy such as NGINX, which handles TLS termination, public
request routing, static files, and access logging.

```text
Clients
   |
   v
Front-end proxy
   |  TLS, routing, static files, access logs
   v
AppServe listeners
   |  HTTP / WebSocket, fixed application or target
   +-- Python worker pool
   +-- PHP worker pool
   +-- Ruby worker pool
   +-- Go / external worker pool

Control API --> Dynamic configuration and runtime statistics
```

Listeners can use TCP or UNIX-domain sockets. Multiple listeners may serve
the same application, and multiple applications can run in one AppServe
instance with separate worker pools and execution environments.

## Quick start

### 1. Build and install

Building requires a C compiler and make. To run the Python example below,
install Python 3 and its development headers and libraries, including
`python3-config`. The API examples use curl with UNIX-socket support.

From the source directory:

```sh
./configure --prefix=/usr/local/appserve
./configure python --config=python3-config
make
sudo make install
```

Configure the language modules you need before running `make`. Use
`./configure --help` for server build options and `./configure python --help`
for Python module options.

### 2. Start the server

Run AppServe in the foreground:

```sh
sudo /usr/local/appserve/sbin/appserved --no-daemon
```

Keep it running and use another terminal for the following steps. With the
build prefix above, the control socket is
`/usr/local/appserve/control.appserve.sock`. Use
`/usr/local/appserve/sbin/appserved --help` to see options and configured
default paths.

### 3. Create an application

Save the following as `/srv/appserve/hello/wsgi.py`. The default application
user is `nobody`; it needs permission to read the file and traverse its parent
directories.

```python
def application(environ, start_response):
    body = b"Hello from AppServe!\n"
    start_response("200 OK", [
        ("Content-Type", "text/plain"),
        ("Content-Length", str(len(body))),
    ])
    return [body]
```

Save this configuration as `config.json`:

```json
{
  "listeners": {
    "127.0.0.1:8080": {
      "pass": "applications/hello"
    }
  },
  "applications": {
    "hello": {
      "type": "python",
      "path": "/srv/appserve/hello",
      "module": "wsgi",
      "callable": "application",
      "processes": {
        "spare": 1,
        "max": 4,
        "idle_timeout": 30
      }
    }
  }
}
```

This pool maintains one spare worker, can grow to four workers as needed,
and reclaims excess workers after 30 seconds of inactivity.

### 4. Apply configuration and send a request

```sh
sudo curl --unix-socket /usr/local/appserve/control.appserve.sock \
    -X PUT -H 'Content-Type: application/json' \
    --data-binary @config.json http://localhost/config

curl http://127.0.0.1:8080/
```

### 5. Inspect and manage the application

Read application runtime statistics:

```sh
sudo curl --unix-socket /usr/local/appserve/control.appserve.sock \
    http://localhost/status/applications/hello
```

Update the process-pool policy while the server is running:

```sh
sudo curl --unix-socket /usr/local/appserve/control.appserve.sock \
    -X PUT -H 'Content-Type: application/json' \
    --data-binary '8' http://localhost/config/applications/hello/processes/max
```

Restart the application, for example after updating its code:

```sh
sudo curl --unix-socket /usr/local/appserve/control.appserve.sock \
    http://localhost/control/applications/hello/restart
```

## Project information

- Source code and issue tracking: https://github.com/hongzhidao/AppServe
- Release history: [CHANGES](CHANGES)
- Release notes and verification details: [docs/release-notes.md](docs/release-notes.md)

Contributions and issue reports are welcome.

## License

AppServe is licensed under the Apache License 2.0. See [LICENSE](LICENSE) and
[NOTICE](NOTICE) for licensing and attribution.
