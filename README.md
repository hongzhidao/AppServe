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

- Total server requests.
- Running, starting, and idle workers for each application.
- Active requests for each application, including requests waiting for a
  worker.

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

The repository is currently private; access is required to view the source,
report issues, and contribute changes.

## License

AppServe is licensed under the Apache License 2.0. See [LICENSE](LICENSE) and
[NOTICE](NOTICE) for licensing and attribution.
