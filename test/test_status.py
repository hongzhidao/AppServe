import os
import signal
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor

from unit.applications.lang.python import ApplicationPython
from unit.option import option
from unit.status import Status

prerequisites = {'modules': {'python': 'any'}}


client = ApplicationPython()


def check_latency(status):
    apps = status['applications'].values()
    for state in [status, *apps]:
        latency = state['latency']
        count = state['requests']['completed'] + state['requests']['failed']
        assert list(latency) == ['sum', 'avg', 'max', 'p95', 'p99']
        assert latency['avg'] == (latency['sum'] // count if count else 0)
        assert all(value >= 0 for value in latency.values())
        assert latency['p95'] <= latency['p99'] <= latency['max']
    assert status['latency']['sum'] == sum(app['latency']['sum'] for app in apps)
    assert status['latency']['max'] == max(
        (app['latency']['max'] for app in apps), default=0
    )


def app_default(name="empty", module="wsgi"):
    return {
        "type": client.get_application_type(),
        "processes": {"spare": 0},
        "path": option.test_dir + "/python/" + name,
        "working_directory": option.test_dir + "/python/" + name,
        "module": module,
    }

def test_status():
    assert 'error' in client.conf_delete('/status'), 'DELETE method'
    assert 'connections' not in client.conf_get('/status')
    assert client.get(**client._get_args('/status/connections'))['status'] == 404

def test_status_requests(skip_alert):
    skip_alert(r'Python failed to import module "blah"')

    def check_requests(empty, blah=0):
        expected = {
            'empty': {
                'total': empty, 'active': 0, 'queued': 0,
                'completed': empty, 'failed': 0,
            },
            'blah': {
                'total': blah, 'active': 0, 'queued': 0,
                'completed': 0, 'failed': blah,
            },
        }
        for _ in range(200):
            status = client.conf_get('/status')
            check_latency(status)
            requests = {
                name: app['requests']
                for name, app in status['applications'].items()
            }
            assert status['requests'] == {
                field: sum(app[field] for app in requests.values())
                for field in ('total', 'active', 'queued', 'completed', 'failed')
            }
            if requests == expected:
                assert status['applications']['empty']['responses'] == {
                    '1xx': 0, '2xx': empty, '3xx': 0, '4xx': 0, '5xx': 0,
                }
                assert status['applications']['blah']['responses'] == {
                    '1xx': 0, '2xx': 0, '3xx': 0, '4xx': 0, '5xx': blah,
                }
                assert status['responses'] == {
                    '1xx': 0, '2xx': empty, '3xx': 0, '4xx': 0, '5xx': blah,
                }
                return
            time.sleep(0.01)
        assert requests == expected

    assert 'success' in client.conf(
        {
            "listeners": {
                "*:8080": {"pass": "applications/empty"},
                "*:8081": {"pass": "applications/empty"},
                "*:8082": {"pass": "applications/blah"},
            },
            "applications": {
                "empty": app_default(),
                "blah": {
                    "type": client.get_application_type(),
                    "processes": {"spare": 0},
                    "module": "blah",
                },
            },
        },
    )

    check_requests(0)

    assert client.get()['status'] == 200
    check_requests(1)

    assert client.get(port=8081)['status'] == 200
    check_requests(2)

    assert (
        client.get(headers={'Host': '/', 'Connection': 'close'})['status']
        == 400
    )
    check_requests(2)

    assert client.get(port=8082)['status'] == 503
    check_requests(2, 1)

    client.http(
        b"""GET / HTTP/1.1
Host: localhost

GET / HTTP/1.1
Host: localhost
Connection: close

""",
        raw=True,
    )
    check_requests(4, 1)

    sock = client.get(port=8081, no_recv=True)
    try:
        check_requests(5, 1)
    finally:
        sock.close()

def test_status_applications():
    def check_applications(expert):
        apps = client.conf_get('/status/applications')
        assert sorted(apps) == sorted(expert)

    def check_application(name, busy, idle, active, total=0, max=1, spare=0,
                          responses=None, queued=0):
        if responses is None:
            responses = total - active
        expected = {
            'processes': {
                'max': max,
                'spare': spare,
                'busy': busy,
                'idle': idle,
                'crash': 0,
            },
            'requests': {
                'total': total,
                'active': active,
                'queued': queued,
                'completed': total - active,
                'failed': 0,
            },
            'responses': {
                '1xx': 0, '2xx': responses, '3xx': 0, '4xx': 0, '5xx': 0,
            },
        }
        for _ in range(200):
            status = client.conf_get(f'/status/applications/{name}')
            status.pop('latency')
            if status == expected:
                return
            time.sleep(0.01)
        assert status == expected

    client.load('delayed')
    Status.init()

    check_applications(['delayed'])
    check_application('delayed', 0, 0, 0)

    # idle

    assert client.get()['status'] == 200
    check_application('delayed', 0, 1, 0, total=1)

    assert 'success' in client.conf('4', 'applications/delayed/processes')
    check_application('delayed', 0, 4, 0, max=4, spare=4)

    # active

    (_, sock) = client.get(
        headers={
            'Host': 'localhost',
            'X-Delay': '2',
            'Connection': 'close',
        },
        start=True,
        read_timeout=1,
    )
    check_application('delayed', 1, 3, 1, total=1, max=4, spare=4, responses=1)
    sock.close()

    # starting

    assert 'success' in client.conf(
        {
            "listeners": {
                "*:8080": {"pass": "applications/restart"},
                "*:8081": {"pass": "applications/delayed"},
            },
            "applications": {
                "restart": app_default("restart", "longstart"),
                "delayed": app_default("delayed"),
            },
        },
    )
    Status.init()

    check_applications(['delayed', 'restart'])
    check_application('restart', 0, 0, 0)
    check_application('delayed', 0, 0, 0)

    client.get(read_timeout=1)

    check_application('restart', 0, 0, 1, total=1, queued=1)
    check_application('delayed', 0, 0, 0)

def test_status_fixed_application():
    assert 'success' in client.conf(
        {
            "listeners": {
                "*:8080": {"pass": "applications/empty"},
                "*:8081": {"pass": "applications/empty"},
            },
            "applications": {
                "empty": app_default(),
            },
        },
    )

    Status.init()

    assert client.get()['status'] == 200
    assert Status.get('/requests/total') == 1, 'fixed application'
    assert client.get(url='/different')['status'] == 200
    assert Status.get('/requests/total') == 2, 'fixed application different URI'


def test_status_requests_queued():
    client.load('restart', module='longstart', processes={'max': 1, 'spare': 0})
    socks = []
    try:
        for _ in range(2):
            socks.append(client.get(no_recv=True))

        for _ in range(100):
            status = client.conf_get('/status')
            app = status['applications']['restart']
            if app['requests'] == {
                'total': 2, 'active': 2, 'queued': 2, 'completed': 0, 'failed': 0,
            }:
                break
            time.sleep(0.01)
        assert app['requests'] == {
            'total': 2, 'active': 2, 'queued': 2, 'completed': 0, 'failed': 0,
        }
        assert app['processes']['busy'] == 0, 'requests queued before worker start'
        assert status['requests'] == app['requests']
        assert app['latency'] == {
            'sum': 0, 'avg': 0, 'max': 0, 'p95': 0, 'p99': 0,
        }

        for sock in socks:
            assert client._resp_to_dict(client.recvall(sock).decode())['status'] == 200
    finally:
        for sock in socks:
            sock.close()

    assert client.conf_get('/status/requests') == {
        'total': 2, 'active': 0, 'queued': 0, 'completed': 2, 'failed': 0,
    }
    latency = client.conf_get('/status/latency')
    assert latency['avg'] == latency['sum'] // 2
    assert latency['sum'] >= 3000, 'latency includes worker startup and queueing'
    assert latency['max'] >= 1500
    assert latency['p95'] == latency['p99'] == latency['max']


def test_status_requests_queued_busy():
    client.load('request_status', processes=1)
    response, busy_sock = client.get(headers={
        'Host': 'localhost', 'X-Delay': '5', 'Connection': 'close',
    }, start=True, raw_resp=True, read_timeout=0.1)
    socks = []

    def wait_requests(expected):
        for _ in range(200):
            status = client.conf_get('/status')
            requests = status['applications']['request_status']['requests']
            assert status['requests'] == requests
            if requests == expected:
                return
            time.sleep(0.01)
        assert requests == expected

    try:
        assert 'ready' in response, 'worker is handling the first request'
        wait_requests({
            'total': 1, 'active': 1, 'queued': 0, 'completed': 0, 'failed': 0,
        })

        for _ in range(3):
            socks.append(client.get(no_recv=True))
        wait_requests({
            'total': 4, 'active': 4, 'queued': 3, 'completed': 0, 'failed': 0,
        })
        assert client.conf_get(
            '/status/applications/request_status/requests/queued'
        ) == 3
        assert client.conf_get('/status/requests/queued') == 3

        assert b'done' in client.recvall(busy_sock)
        for sock in socks:
            assert client._resp_to_dict(client.recvall(sock).decode())['status'] == 200
        wait_requests({
            'total': 4, 'active': 0, 'queued': 0, 'completed': 4, 'failed': 0,
        })
    finally:
        busy_sock.close()
        for sock in socks:
            sock.close()


def test_status_requests_queued_startup_failed(skip_alert):
    skip_alert(r'Python failed to import module "wsgi"')
    client.load('queue_start_error', processes={'max': 1, 'spare': 0})
    socks = []
    try:
        for _ in range(3):
            socks.append(client.get(no_recv=True))

        for _ in range(100):
            status = client.conf_get('/status')
            requests = status['applications']['queue_start_error']['requests']
            assert status['requests'] == requests
            if requests['queued'] == 3:
                break
            time.sleep(0.01)
        assert requests == {
            'total': 3, 'active': 3, 'queued': 3, 'completed': 0, 'failed': 0,
        }

        for sock in socks:
            assert client._resp_to_dict(client.recvall(sock).decode())['status'] == 503
    finally:
        for sock in socks:
            sock.close()

    assert client.conf_get('/status/requests') == {
        'total': 3, 'active': 0, 'queued': 0, 'completed': 0, 'failed': 3,
    }
    assert client.conf_get(
        '/status/applications/queue_start_error/requests/queued'
    ) == 0


def test_status_requests_queued_global():
    apps = {name: app_default('exit_code') for name in ('orders', 'users')}
    for app in apps.values():
        app['processes'] = 1
    assert 'success' in client.conf({
        'listeners': {
            '*:8080': {'pass': 'applications/orders'},
            '*:8081': {'pass': 'applications/users'},
        },
        'applications': apps,
    })
    pids = []
    socks = []
    try:
        for port in (8080, 8081):
            pid = int(client.get(port=port)['headers']['X-Pid'])
            pids.append(pid)
            os.kill(pid, signal.SIGSTOP)

        for port in (8080, 8081, 8081):
            socks.append(client.get(port=port, no_recv=True))

        for _ in range(200):
            status = client.conf_get('/status')
            queued = {
                name: app['requests']['queued']
                for name, app in status['applications'].items()
            }
            assert status['requests']['queued'] == sum(queued.values())
            if queued == {'orders': 1, 'users': 2}:
                break
            time.sleep(0.01)
        assert queued == {'orders': 1, 'users': 2}
        assert status['requests']['queued'] == 3
        assert status['requests']['active'] == 3

        for pid in pids:
            os.kill(pid, signal.SIGCONT)
        pids.clear()
        for sock in socks:
            assert client._resp_to_dict(client.recvall(sock).decode())['status'] == 200
    finally:
        for pid in pids:
            os.kill(pid, signal.SIGCONT)
        for sock in socks:
            sock.close()

    assert client.conf_get('/status/requests') == {
        'total': 5, 'active': 0, 'queued': 0, 'completed': 5, 'failed': 0,
    }


def test_status_requests_outcomes():
    client.load('request_status')
    for status in (200, 201, 204, 302, 304, 404, 499, 500, 599):
        assert client.get(headers={
            'Host': 'localhost', 'X-Status': str(status), 'Connection': 'close',
        })['status'] == status
    expected = {'total': 9, 'active': 0, 'queued': 0, 'completed': 9, 'failed': 0}
    assert client.conf_get('/status/requests') == expected
    assert client.conf_get('/status/applications/request_status/requests') == expected
    responses = {'1xx': 0, '2xx': 3, '3xx': 2, '4xx': 2, '5xx': 2}
    assert client.conf_get('/status/responses') == responses
    assert client.conf_get('/status/applications/request_status/responses') == responses
    assert client.conf_get('/status/responses/2xx') == 3

    assert client.get(headers={
        'Host': 'localhost', 'X-Invalid-Status': '1', 'Connection': 'close',
    })['status'] == 503
    expected = {'total': 10, 'active': 0, 'queued': 0, 'completed': 9, 'failed': 1}
    assert client.conf_get('/status/requests') == expected
    assert client.conf_get('/status/applications/request_status/requests') == expected
    responses['5xx'] += 1
    assert client.conf_get('/status/responses') == responses
    assert client.conf_get('/status/applications/request_status/responses') == responses

    for status in (600, 999):
        assert client.get(headers={
            'Host': 'localhost', 'X-Status': str(status), 'Connection': 'close',
        })['status'] == status
    assert client.conf_get('/status/responses') == responses


def test_status_requests_stream_error():
    client.load('iter_exception')
    response = client.get(headers={
        'Host': 'localhost', 'X-Skip': '2', 'X-Chunked': '1', 'Connection': 'close',
    }, raw_resp=True)
    if response:
        assert response[-5:] != '0\r\n\r\n', 'response body incomplete'
    assert client.conf_get('/status/requests') == {
        'total': 1, 'active': 0, 'queued': 0, 'completed': 0, 'failed': 1,
    }
    assert client.conf_get('/status/responses') == {
        '1xx': 0, '2xx': 1, '3xx': 0, '4xx': 0, '5xx': 0,
    }
    assert client.get(headers={
        'Host': 'localhost', 'X-Skip': '9', 'X-Chunked': '1', 'Connection': 'close',
    })['status'] == 200
    assert client.conf_get('/status/requests') == {
        'total': 2, 'active': 0, 'queued': 0, 'completed': 1, 'failed': 1,
    }
    assert client.conf_get('/status/responses') == {
        '1xx': 0, '2xx': 2, '3xx': 0, '4xx': 0, '5xx': 0,
    }


def test_status_requests_timeout():
    client.load('single_thread', processes=1, limits={'timeout': 1})
    assert client.get(headers={
        'Host': 'localhost', 'X-Delay': '3', 'Connection': 'close',
    })['status'] == 503
    expected = {'total': 1, 'active': 0, 'queued': 0, 'completed': 0, 'failed': 1}
    assert client.conf_get('/status/requests') == expected
    latency = client.conf_get('/status/latency')
    assert 800 <= latency['max'] < 2000, 'failed request timed until timeout'
    assert latency['sum'] == latency['avg'] == latency['max']
    assert latency['p95'] == latency['p99'] == latency['max']
    time.sleep(3)
    assert client.conf_get('/status/requests') == expected, 'late response not counted'
    assert client.conf_get('/status/latency') == latency, 'late response not timed'
    assert client.conf_get('/status/responses') == {
        '1xx': 0, '2xx': 0, '3xx': 0, '4xx': 0, '5xx': 1,
    }


def test_status_requests_cancelled():
    client.load('request_status')
    response, sock = client.get(headers={
        'Host': 'localhost', 'X-Delay': '2', 'Connection': 'close',
    }, start=True, raw_resp=True, read_timeout=0.1)
    try:
        assert 'ready' in response
        assert client.conf_get('/status/requests') == {
            'total': 1, 'active': 1, 'queued': 0, 'completed': 0, 'failed': 0,
        }
        assert client.conf_get('/status/latency') == {
            'sum': 0, 'avg': 0, 'max': 0, 'p95': 0, 'p99': 0,
        }
        assert client.conf_get('/status/responses') == {
            '1xx': 0, '2xx': 1, '3xx': 0, '4xx': 0, '5xx': 0,
        }
    finally:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        sock.close()

    expected = {'total': 1, 'active': 0, 'queued': 0, 'completed': 0, 'failed': 1}
    for _ in range(300):
        requests = client.conf_get('/status/requests')
        if requests == expected:
            break
        time.sleep(0.01)
    assert requests == expected
    latency = client.conf_get('/status/latency')
    assert latency['sum'] == latency['avg'] == latency['max']
    assert latency['p95'] == latency['p99'] == latency['max']
    assert client.conf_get('/status/responses') == {
        '1xx': 0, '2xx': 1, '3xx': 0, '4xx': 0, '5xx': 0,
    }


def test_status_requests_reconfigure():
    def check_requests(expected):
        expected_responses = {
            name: {'1xx': 0, '2xx': app['total'], '3xx': 0, '4xx': 0, '5xx': 0}
            for name, app in expected.items()
        }
        for _ in range(200):
            status = client.conf_get('/status')
            check_latency(status)
            requests = {
                name: app['requests']
                for name, app in status['applications'].items()
            }
            assert status['requests'] == {
                field: sum(app[field] for app in requests.values())
                for field in ('total', 'active', 'queued', 'completed', 'failed')
            }
            assert status['responses'] == {
                field: sum(app['responses'][field]
                           for app in status['applications'].values())
                for field in ('1xx', '2xx', '3xx', '4xx', '5xx')
            }
            responses = {
                name: app['responses']
                for name, app in status['applications'].items()
            }
            if requests == expected and responses == expected_responses:
                return
            time.sleep(0.01)
        assert requests == expected
        assert responses == expected_responses

    apps = {'orders': app_default('delayed'), 'users': app_default()}
    apps['orders']['processes'] = 1
    apps['users']['processes'] = 1
    assert 'success' in client.conf({
        'listeners': {
            '*:8080': {'pass': 'applications/orders'},
            '*:8081': {'pass': 'applications/users'},
        },
        'applications': apps,
    })

    sock = client.get(headers={
        'Host': 'localhost', 'X-Delay': '3', 'Connection': 'close',
    }, no_recv=True)
    try:
        for _ in range(2):
            assert client.get(port=8081)['status'] == 200
        check_requests({
            'orders': {
                'total': 1, 'active': 1, 'queued': 0, 'completed': 0, 'failed': 0,
            },
            'users': {
                'total': 2, 'active': 0, 'queued': 0, 'completed': 2, 'failed': 0,
            },
        })

        apps['orders']['environment'] = {'REVISION': '2'}
        assert 'success' in client.conf(apps['orders'], 'applications/orders')
        check_requests({
            'orders': {
                'total': 0, 'active': 0, 'queued': 0, 'completed': 0, 'failed': 0,
            },
            'users': {
                'total': 2, 'active': 0, 'queued': 0, 'completed': 2, 'failed': 0,
            },
        })
        assert client._resp_to_dict(client.recvall(sock).decode())['status'] == 200
    finally:
        sock.close()

    assert 'success' in client.conf_get('/control/applications/users/restart')
    assert 'success' in client.conf(
        {'pass': 'applications/users'}, 'listeners/*:8080'
    )
    check_requests({
        'orders': {
            'total': 0, 'active': 0, 'queued': 0, 'completed': 0, 'failed': 0,
        },
        'users': {
            'total': 2, 'active': 0, 'queued': 0, 'completed': 2, 'failed': 0,
        },
    })
    assert client.get()['status'] == 200
    check_requests({
        'orders': {
            'total': 0, 'active': 0, 'queued': 0, 'completed': 0, 'failed': 0,
        },
        'users': {
            'total': 3, 'active': 0, 'queued': 0, 'completed': 3, 'failed': 0,
        },
    })

    assert 'success' in client.conf({}, 'listeners')
    assert 'success' in client.conf_delete('applications/users')
    check_requests({
        'orders': {
            'total': 0, 'active': 0, 'queued': 0, 'completed': 0, 'failed': 0,
        },
    })
    assert 'success' in client.conf_delete('applications/orders')
    check_requests({})
    assert client.conf_get('/status/latency') == {
        'sum': 0, 'avg': 0, 'max': 0, 'p95': 0, 'p99': 0,
    }


def test_status_latency():
    apps = {name: app_default('single_thread') for name in ('slow', 'fast')}
    for app in apps.values():
        app['processes'] = 1
    assert 'success' in client.conf({
        'listeners': {
            '*:8080': {'pass': 'applications/slow'},
            '*:8081': {'pass': 'applications/fast'},
        },
        'applications': apps,
    })
    assert client.conf_get('/status/latency') == {
        'sum': 0, 'avg': 0, 'max': 0, 'p95': 0, 'p99': 0,
    }

    for delay in ('0.1', '0.3'):
        assert client.get(headers={
            'Host': 'localhost', 'X-Delay': delay, 'Connection': 'close',
        })['status'] == 200
    assert client.get(port=8081, headers={
        'Host': 'localhost', 'X-Delay': '0.05', 'Connection': 'close',
    })['status'] == 200

    status = client.conf_get('/status')
    check_latency(status)
    slow = status['applications']['slow']['latency']
    fast = status['applications']['fast']['latency']
    assert slow['sum'] >= 350
    assert slow['max'] >= 250
    assert fast['max'] >= 40
    assert slow['p95'] == slow['p99'] == slow['max']
    assert fast['p95'] == fast['p99'] == fast['max']
    assert status['latency']['p95'] == status['latency']['p99'] == slow['max']
    assert status['latency']['avg'] == (slow['sum'] + fast['sum']) // 3
    assert client.conf_get('/status/applications/slow/latency') == slow


def test_status_latency_percentiles():
    apps = {name: app_default('single_thread') for name in ('mixed', 'fast')}
    for app in apps.values():
        app['processes'] = 1
    assert 'success' in client.conf({
        'listeners': {
            '*:8080': {'pass': 'applications/mixed'},
            '*:8081': {'pass': 'applications/fast'},
        },
        'applications': apps,
    })

    # Mixed: 94 fast, 4 medium, 2 slow. Fast: 100 fast.
    for port, delays in (
        (8080, [0.01] * 94 + [0.1] * 4 + [0.4] * 2),
        (8081, [0.01] * 100),
    ):
        for delay in delays:
            assert client.get(port=port, headers={
                'Host': 'localhost', 'X-Delay': str(delay), 'Connection': 'close',
            })['status'] == 200

    status = client.conf_get('/status')
    check_latency(status)
    mixed = status['applications']['mixed']['latency']
    fast = status['applications']['fast']['latency']
    assert 80 <= mixed['p95'] < 250
    assert 350 <= mixed['p99'] < 650
    assert fast['p95'] < 80 and fast['p99'] < 80
    assert status['latency']['p95'] < 80, 'global rank uses merged samples'
    assert 80 <= status['latency']['p99'] < 250
    assert client.conf_get('/status/applications/mixed/latency/p95') == mixed['p95']
    assert client.conf_get('/status/latency/p99') == status['latency']['p99']

    assert 'success' in client.conf_get('/control/applications/mixed/restart')
    assert 'success' in client.conf(
        {'pass': 'applications/mixed'}, 'listeners/*:8081'
    )
    assert client.conf_get('/status/applications/mixed/latency') == mixed

    apps['mixed']['environment'] = {'REVISION': '2'}
    assert 'success' in client.conf(apps['mixed'], 'applications/mixed')
    assert client.conf_get('/status/applications/mixed/latency') == {
        'sum': 0, 'avg': 0, 'max': 0, 'p95': 0, 'p99': 0,
    }
    assert client.conf_get('/status/latency') == fast, 'old latency excluded'
    assert 'success' in client.conf_delete('applications/fast')
    assert client.conf_get('/status/latency') == {
        'sum': 0, 'avg': 0, 'max': 0, 'p95': 0, 'p99': 0,
    }


def test_status_latency_many_applications():
    # Bucket snapshots for eight apps exceed a single port message.
    apps = {f'app{i}': app_default() for i in range(8)}
    assert 'success' in client.conf({
        'listeners': {
            f'*:{8080 + i}': {'pass': f'applications/app{i}'}
            for i in range(8)
        },
        'applications': apps,
    })

    for i in range(8):
        assert client.get(port=8080 + i)['status'] == 200

    status = client.conf_get('/status')
    check_latency(status)
    assert set(status['applications']) == set(apps)
    assert status['requests'] == {
        'total': 8, 'active': 0, 'queued': 0, 'completed': 8, 'failed': 0,
    }
    latency = status['latency']
    assert latency['p95'] == latency['p99'] == latency['max']

    for name, app in status['applications'].items():
        assert app['requests'] == {
            'total': 1, 'active': 0, 'queued': 0, 'completed': 1, 'failed': 0,
        }
        latency = app['latency']
        assert latency['sum'] == latency['avg'] == latency['max']
        assert latency['p95'] == latency['p99'] == latency['max']
        assert client.conf_get(f'/status/applications/{name}/latency') == latency


def test_status_processes_global():
    def wait_processes(expected):
        expected = {
            name: {**state, 'crash': 0} for name, state in expected.items()
        }
        for _ in range(200):
            status = client.conf_get('/status')
            processes = {
                name: app['processes']
                for name, app in status['applications'].items()
            }
            for state in processes.values():
                assert list(state) == ['max', 'spare', 'busy', 'idle', 'crash']
                assert all(count >= 0 for count in state.values())
                assert state['spare'] <= state['max']
            assert status['processes'] == {
                field: sum(state[field] for state in processes.values())
                for field in ('busy', 'idle', 'crash')
            }, 'global is the app snapshot sum'
            if processes == expected:
                return status
            time.sleep(0.01)
        assert processes == expected

    apps = {'orders': app_default('delayed'), 'users': app_default()}
    apps['orders']['processes'] = 2
    apps['users']['processes'] = 1
    assert 'success' in client.conf({
        'listeners': {
            '*:8080': {'pass': 'applications/orders'},
            '*:8081': {'pass': 'applications/users'},
        },
        'applications': apps,
    })
    wait_processes({
        'orders': {'max': 2, 'spare': 2, 'busy': 0, 'idle': 2},
        'users': {'max': 1, 'spare': 1, 'busy': 0, 'idle': 1},
    })
    assert client.conf_get('/status/processes') == {'busy': 0, 'idle': 3, 'crash': 0}

    sock = client.get(headers={
        'Host': 'localhost', 'X-Delay': '1', 'Connection': 'close',
    }, no_recv=True)
    try:
        wait_processes({
            'orders': {'max': 2, 'spare': 2, 'busy': 1, 'idle': 1},
            'users': {'max': 1, 'spare': 1, 'busy': 0, 'idle': 1},
        })
        assert client.conf_get('/status/applications/orders/processes/busy') == 1
        assert client._resp_to_dict(client.recvall(sock).decode())['status'] == 200
    finally:
        sock.close()
    wait_processes({
        'orders': {'max': 2, 'spare': 2, 'busy': 0, 'idle': 2},
        'users': {'max': 1, 'spare': 1, 'busy': 0, 'idle': 1},
    })
    assert 'success' in client.conf('3', 'applications/orders/processes')
    wait_processes({
        'orders': {'max': 3, 'spare': 3, 'busy': 0, 'idle': 3},
        'users': {'max': 1, 'spare': 1, 'busy': 0, 'idle': 1},
    })
    assert 'success' in client.conf(
        {'max': 4, 'spare': 1}, 'applications/orders/processes'
    )
    wait_processes({
        'orders': {'max': 4, 'spare': 1, 'busy': 0, 'idle': 1},
        'users': {'max': 1, 'spare': 1, 'busy': 0, 'idle': 1},
    })
    assert client.conf_get('/status/applications/orders/processes/max') == 4
    assert client.conf_get('/status/applications/orders/processes/spare') == 1
    assert client.get()['status'] == 200
    wait_processes({
        'orders': {'max': 4, 'spare': 1, 'busy': 0, 'idle': 2},
        'users': {'max': 1, 'spare': 1, 'busy': 0, 'idle': 1},
    })
    assert 'success' in client.conf({'listeners': {}, 'applications': {}})
    wait_processes({})


def test_status_processes_crash(skip_alert):
    apps = {name: app_default('exit_code') for name in ('orders', 'users')}
    for app in apps.values():
        app['processes'] = 1
    assert 'success' in client.conf({
        'listeners': {
            '*:8080': {'pass': 'applications/orders'},
            '*:8081': {'pass': 'applications/users'},
        },
        'applications': apps,
    })

    def wait_crashes(expected):
        for _ in range(200):
            status = client.conf_get('/status')
            counts = {
                name: app['processes']['crash']
                for name, app in status['applications'].items()
            }
            assert status['processes']['crash'] == sum(counts.values())
            if counts == expected:
                return
            time.sleep(0.01)
        assert counts == expected

    wait_crashes({'orders': 0, 'users': 0})

    response = client.get()
    assert response['status'] == 200
    pid = int(response['headers']['X-Pid'])
    skip_alert(r'(?:app )?process %s exited on signal 9' % pid)
    os.kill(pid, signal.SIGKILL)
    wait_crashes({'orders': 1, 'users': 0})
    assert client.get()['status'] == 200, 'worker respawned'

    assert client.get(headers={
        'Host': 'localhost', 'X-Exit-Code': '7', 'Connection': 'close',
    })['status'] == 503
    wait_crashes({'orders': 2, 'users': 0})
    assert client.get(port=8081, headers={
        'Host': 'localhost', 'X-Exit-Code': '3', 'Connection': 'close',
    })['status'] == 503
    wait_crashes({'orders': 2, 'users': 1})
    assert client.conf_get('/status/applications/orders/processes/crash') == 2
    assert client.conf_get('/status/processes/crash') == 3

    # A zero exit is not a crash, even if it interrupts a request.
    assert client.get(headers={
        'Host': 'localhost', 'X-Exit-Code': '0', 'Connection': 'close',
    })['status'] == 503
    assert client.get()['status'] == 200
    wait_crashes({'orders': 2, 'users': 1})

    assert 'success' in client.conf_get('/control/applications/orders/restart')
    assert 'success' in client.conf(
        {'pass': 'applications/orders'}, 'listeners/*:8081'
    )
    assert client.get()['status'] == 200
    wait_crashes({'orders': 2, 'users': 1})

    apps['orders']['environment'] = {'REVISION': '2'}
    assert 'success' in client.conf(apps['orders'], 'applications/orders')
    wait_crashes({'orders': 0, 'users': 1})
    assert 'success' in client.conf_delete('applications/users')
    wait_crashes({'orders': 0})


def test_status_processes_crash_normal_recycling():
    client.load('exit_code', processes=1, limits={'requests': 1})
    pids = set()
    for _ in range(3):
        response = client.get()
        assert response['status'] == 200
        pids.add(response['headers']['X-Pid'])
    assert len(pids) == 3, 'request limit recycled workers'
    assert client.conf_get('/status/applications/exit_code/processes/crash') == 0
    assert client.conf_get('/status/processes/crash') == 0

    client.load('exit_code', processes={'max': 1, 'spare': 0, 'idle_timeout': 1})
    assert client.get()['status'] == 200
    for _ in range(300):
        processes = client.conf_get('/status/applications/exit_code/processes')
        if processes['busy'] == processes['idle'] == 0:
            break
        time.sleep(0.01)
    assert processes == {'max': 1, 'spare': 0, 'busy': 0, 'idle': 0, 'crash': 0}
    assert client.conf_get('/status/processes/crash') == 0


def test_status_processes_sampling():
    client.load('empty', processes={'max': 4, 'spare': 0, 'idle_timeout': 1})

    def send_requests():
        for _ in range(100):
            assert client.get()['status'] == 200

    def sample_status():
        status = client.conf_get('/status')
        check_latency(status)
        app = status['applications']['empty']
        processes = app['processes']
        assert processes['max'] == 4
        assert processes['spare'] == 0
        assert 0 <= processes['busy'] <= 4
        assert 0 <= processes['idle'] <= 4
        assert processes['crash'] == 0
        assert 0 <= app['requests']['active'] <= 4
        assert 0 <= app['requests']['queued'] <= 4
        assert status['requests'] == app['requests']
        assert status['responses'] == app['responses']
        assert 0 <= app['responses']['2xx'] <= 400
        for field in ('1xx', '3xx', '4xx', '5xx'):
            assert app['responses'][field] == 0
        assert status['processes'] == {
            'busy': processes['busy'],
            'idle': processes['idle'],
            'crash': 0,
        }
        return app

    with ThreadPoolExecutor(max_workers=4) as executor:
        requests = [executor.submit(send_requests) for _ in range(4)]
        while True:
            sample_status()
            if all(request.done() for request in requests):
                break
            time.sleep(0.001)
        for request in requests:
            request.result()

    expected = {
        'processes': {'max': 4, 'spare': 0, 'busy': 0, 'idle': 0, 'crash': 0},
        'requests': {
            'total': 400, 'active': 0, 'queued': 0, 'completed': 400, 'failed': 0,
        },
    }
    for _ in range(300):
        app = sample_status()
        state = {field: app[field] for field in expected}
        if state == expected:
            assert app['responses']['2xx'] > 0
            return
        time.sleep(0.01)
    assert state == expected
