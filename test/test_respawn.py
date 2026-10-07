import re
import subprocess
import time

import pytest
from unit.applications.lang.python import ApplicationPython

prerequisites = {'modules': {'python': 'any'}}


client = ApplicationPython()


PATTERN_ROUTER = 'appserve: router'
PATTERN_CONTROLLER = 'appserve: controller'

@pytest.fixture(autouse=True)
def setup_method_fixture(temp_dir):
    client.app_name = f'app-{temp_dir.split("/")[-1]}'

    client.load('empty', client.app_name)

    assert 'success' in client.conf(
        '1', 'applications/' + client.app_name + '/processes'
    )

def pid_by_name(name, ppid):
    output = subprocess.check_output(['ps', 'axww', '-O', 'ppid']).decode()
    m = re.search(r'\s*(\d+)\s*' + str(ppid) + r'.*' + name, output)
    return None if m is None else m.group(1)

def kill_pids(*pids):
    subprocess.call(['kill', '-9'] + list(pids))

def wait_for_process(process, unit_pid):
    for _ in range(50):
        found = pid_by_name(process, unit_pid)

        if found is not None:
            break

        time.sleep(0.1)

    return found

def find_proc(name, ppid, ps_output):
    return re.findall(str(ppid) + r'.*' + name, ps_output)

def smoke_test(unit_pid):
    for _ in range(10):
        r = client.conf('1', 'applications/' + client.app_name + '/processes')

        if 'success' in r:
            break

        time.sleep(0.1)

    assert 'success' in r
    assert client.get()['status'] == 200

    # Check if the only one router, controller,
    # and application processes running.

    out = subprocess.check_output(['ps', 'ax', '-O', 'ppid']).decode()
    assert len(find_proc(PATTERN_ROUTER, unit_pid, out)) == 1
    assert len(find_proc(PATTERN_CONTROLLER, unit_pid, out)) == 1
    assert len(find_proc(client.app_name, unit_pid, out)) == 1

def test_respawn_router(skip_alert, unit_pid, skip_fds_check):
    skip_fds_check(router=True)
    pid = pid_by_name(PATTERN_ROUTER, unit_pid)

    kill_pids(pid)
    skip_alert(r'process %s exited on signal 9' % pid)

    assert wait_for_process(PATTERN_ROUTER, unit_pid) is not None

    smoke_test(unit_pid)

    assert client.conf_get('/status/processes/crash') == 0

def test_respawn_controller(skip_alert, unit_pid, skip_fds_check):
    skip_fds_check(controller=True)
    pid = pid_by_name(PATTERN_CONTROLLER, unit_pid)

    kill_pids(pid)
    skip_alert(r'process %s exited on signal 9' % pid)

    assert (
        wait_for_process(PATTERN_CONTROLLER, unit_pid)
        is not None
    )

    assert client.get()['status'] == 200

    smoke_test(unit_pid)

    assert client.conf_get('/status/processes/crash') == 0

def test_respawn_application(skip_alert, unit_pid):
    pid = pid_by_name(client.app_name, unit_pid)

    kill_pids(pid)
    skip_alert(r'process %s exited on signal 9' % pid)

    assert wait_for_process(client.app_name, unit_pid) is not None

    assert client.conf_get('/status/processes/crash') == 0, 'prototype excluded'

    smoke_test(unit_pid)

@pytest.mark.parametrize('worker', [False, True])
def test_respawn_application_inflight_failed(skip_alert, unit_pid, worker):
    client.app_name += '-failed-' + str(int(worker))
    client.load('single_thread', client.app_name, processes=1)
    sock = client.get(headers={
        'Host': 'localhost', 'X-Delay': '5', 'Connection': 'close',
    }, no_recv=True)
    try:
        for _ in range(100):
            status = client.conf_get('/status/applications/' + client.app_name)
            if (status['requests']['active'] == 1
                    and status['processes']['busy'] == 1):
                break
            time.sleep(0.01)
        assert status['requests']['active'] == 1
        assert status['processes']['busy'] == 1
        assert status['processes']['idle'] == 0

        if worker:
            output = subprocess.check_output(['ps', 'axww']).decode()
            match = re.search(
                r'^\s*(\d+).*appserve: "' + client.app_name + r'" application',
                output,
                re.M,
            )
            assert match is not None
            pid = match.group(1)
        else:
            pid = pid_by_name(client.app_name, unit_pid)
        assert pid is not None
        skip_alert(r'(?:app )?process %s exited on signal 9' % pid)
        kill_pids(pid)
        assert client._resp_to_dict(client.recvall(sock).decode())['status'] == 503
    finally:
        sock.close()

    assert client.conf_get('/status/requests') == {
        'total': 1, 'active': 0, 'queued': 0, 'completed': 0, 'failed': 1,
    }
    assert client.conf_get('/status/applications/' + client.app_name
                           + '/processes/crash') == int(worker)
    assert client.get()['status'] == 200
    assert client.conf_get('/status/requests') == {
        'total': 2, 'active': 0, 'queued': 0, 'completed': 1, 'failed': 1,
    }


def test_respawn_application_inflight_removed(skip_alert, unit_pid):
    client.load('single_thread', client.app_name, processes=1)

    sock = client.get(
        headers={
            'Host': 'localhost',
            'X-Delay': '5',
            'Connection': 'close',
        },
        no_recv=True,
    )

    try:
        for _ in range(100):
            status = client.conf_get('/status/applications/' + client.app_name)
            if (status['requests']['active'] == 1
                    and status['processes']['idle'] == 0):
                break
            time.sleep(0.01)

        assert status['requests']['active'] == 1, 'request acknowledged'
        assert status['processes']['idle'] == 0, 'worker handling request'

        output = subprocess.check_output(['ps', 'axww']).decode()
        match = re.search(
            r'^\s*(\d+).*appserve: "' + client.app_name + r'" application',
            output,
            re.M,
        )
        assert match is not None, 'worker exists'
        pid = match.group(1)

        assert 'success' in client.conf({'listeners': {}, 'applications': {}})
        skip_alert(r'app process %s exited on signal 9' % pid)
        kill_pids(pid)

        response = client._resp_to_dict(client.recvall(sock).decode())
        assert response['status'] == 503, 'in-flight request failed'
    finally:
        sock.close()

    client.load('empty', client.app_name, processes=1)
    assert client.get()['status'] == 200, 'router still works'
    assert client.conf_get('/status/processes/crash') == 0, 'old app excluded'
