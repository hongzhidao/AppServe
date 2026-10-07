import time
from concurrent.futures import ThreadPoolExecutor

from unit.applications.lang.python import ApplicationPython
from unit.option import option
from unit.status import Status

prerequisites = {'modules': {'python': 'any'}}


client = ApplicationPython()


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
            'empty': {'total': empty, 'active': 0},
            'blah': {'total': blah, 'active': 0},
        }
        for _ in range(200):
            status = client.conf_get('/status')
            requests = {
                name: app['requests']
                for name, app in status['applications'].items()
            }
            assert status['requests'] == {
                field: sum(app[field] for app in requests.values())
                for field in ('total', 'active')
            }
            if requests == expected:
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

    def check_application(name, busy, idle, active, total=0, max=1, spare=0):
        expected = {
            'processes': {
                'max': max,
                'spare': spare,
                'busy': busy,
                'idle': idle,
            },
            'requests': {'total': total, 'active': active},
        }
        for _ in range(200):
            status = client.conf_get(f'/status/applications/{name}')
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
    check_application('delayed', 1, 3, 1, total=1, max=4, spare=4)
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

    check_application('restart', 0, 0, 1, total=1)
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
            if app['requests'] == {'total': 2, 'active': 2}:
                break
            time.sleep(0.01)
        assert app['requests'] == {'total': 2, 'active': 2}
        assert app['processes']['busy'] == 0, 'requests queued before worker start'
        assert status['requests'] == app['requests']

        for sock in socks:
            assert client._resp_to_dict(client.recvall(sock).decode())['status'] == 200
    finally:
        for sock in socks:
            sock.close()

    assert client.conf_get('/status/requests') == {'total': 2, 'active': 0}


def test_status_requests_reconfigure():
    def check_requests(expected):
        for _ in range(200):
            status = client.conf_get('/status')
            requests = {
                name: app['requests']
                for name, app in status['applications'].items()
            }
            assert status['requests'] == {
                field: sum(app[field] for app in requests.values())
                for field in ('total', 'active')
            }
            if requests == expected:
                return
            time.sleep(0.01)
        assert requests == expected

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
            'orders': {'total': 1, 'active': 1},
            'users': {'total': 2, 'active': 0},
        })

        apps['orders']['environment'] = {'REVISION': '2'}
        assert 'success' in client.conf(apps['orders'], 'applications/orders')
        check_requests({
            'orders': {'total': 0, 'active': 0},
            'users': {'total': 2, 'active': 0},
        })
        assert client._resp_to_dict(client.recvall(sock).decode())['status'] == 200
    finally:
        sock.close()

    assert 'success' in client.conf_get('/control/applications/users/restart')
    assert 'success' in client.conf(
        {'pass': 'applications/users'}, 'listeners/*:8080'
    )
    check_requests({
        'orders': {'total': 0, 'active': 0},
        'users': {'total': 2, 'active': 0},
    })
    assert client.get()['status'] == 200
    check_requests({
        'orders': {'total': 0, 'active': 0},
        'users': {'total': 3, 'active': 0},
    })

    assert 'success' in client.conf({}, 'listeners')
    assert 'success' in client.conf_delete('applications/users')
    check_requests({'orders': {'total': 0, 'active': 0}})
    assert 'success' in client.conf_delete('applications/orders')
    check_requests({})


def test_status_processes_global():
    def wait_processes(expected):
        for _ in range(200):
            status = client.conf_get('/status')
            processes = {
                name: app['processes']
                for name, app in status['applications'].items()
            }
            for state in processes.values():
                assert list(state) == ['max', 'spare', 'busy', 'idle']
                assert all(count >= 0 for count in state.values())
                assert state['spare'] <= state['max']
            assert status['processes'] == {
                field: sum(state[field] for state in processes.values())
                for field in ('busy', 'idle')
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
    assert client.conf_get('/status/processes') == {'busy': 0, 'idle': 3}

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


def test_status_processes_sampling():
    client.load('empty', processes={'max': 4, 'spare': 0, 'idle_timeout': 1})

    def send_requests():
        for _ in range(100):
            assert client.get()['status'] == 200

    def sample_status():
        status = client.conf_get('/status')
        app = status['applications']['empty']
        processes = app['processes']
        assert processes['max'] == 4
        assert processes['spare'] == 0
        assert 0 <= processes['busy'] <= 4
        assert 0 <= processes['idle'] <= 4
        assert 0 <= app['requests']['active'] <= 4
        assert status['requests'] == app['requests']
        assert status['processes'] == {
            'busy': processes['busy'],
            'idle': processes['idle'],
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
        'processes': {'max': 4, 'spare': 0, 'busy': 0, 'idle': 0},
        'requests': {'total': 400, 'active': 0},
    }
    for _ in range(300):
        app = sample_status()
        if app == expected:
            return
        time.sleep(0.01)
    assert app == expected
