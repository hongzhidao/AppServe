import json
import time

import pytest
from unit.applications.proto import ApplicationProto


client = ApplicationProto()


@pytest.fixture(autouse=True)
def setup_method_fixture():
    assert 'success' in client.conf(
        {
            'listeners': {'*:8080': {'pass': 'routes'}},
            'routes': [{'action': {'return': 200}}],
        },
    ), 'configure routes'

def set_variable(template, value):
    assert 'success' in client.conf(
        {
            'listeners': {'*:8080': {'pass': 'routes/entry'}},
            'routes': {
                'entry': [{'action': {'pass': template}}],
                value: [{'action': {'return': 200}}],
            },
        },
    ), 'configure variable route'

def set_condition(expression):
    assert 'success' in client.conf(
        [{'match': {'if': expression}, 'action': {'return': 200}}], 'routes'
    ), 'configure variable condition'

def test_variables_request_time(require):
    require({'modules': {'njs': 'any'}})

    set_condition('`${Number(vars.request_time) >= 1}`')
    assert client.get()['status'] == 404

    sock = client.http(b'G', no_recv=True, raw=True)
    time.sleep(1.1)
    assert client.http(
        b'ET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n',
        sock=sock,
        raw=True,
    )['status'] == 200

def test_variables_method():
    set_variable('routes/$method', 'GET')
    assert client.get()['status'] == 200
    assert client.post()['status'] == 404

    set_variable('routes/$method', 'POST')
    assert client.get()['status'] == 404
    assert client.post()['status'] == 200

@pytest.mark.parametrize(
    'uri, value',
    [('/3', '3'), ('/4*', '4*'), ('/5%2A', '5*'), ('/9?q#a', '9')],
)
def test_variables_uri(uri, value):
    set_variable('routes$uri', value)
    assert client.get(url=uri)['status'] == 200
    assert client.get(url='/different')['status'] == 404

@pytest.mark.parametrize(
    'host, value',
    [
        ('localhost', 'localhost'),
        ('localhost1.', 'localhost1'),
        ('localhost2:8080', 'localhost2'),
        ('.localhost', '.localhost'),
        ('www.localhost', 'www.localhost'),
    ],
)
def test_variables_host(host, value):
    set_variable('routes/$host', value)
    assert client.get(headers={'Host': host, 'Connection': 'close'})[
        'status'
    ] == 200
    assert client.get(headers={'Host': 'different', 'Connection': 'close'})[
        'status'
    ] == 404

def test_variables_remote_addr():
    set_variable('routes/$remote_addr', '127.0.0.1')
    assert client.get()['status'] == 200

    assert 'success' in client.conf(
        {'[::1]:8080': {'pass': 'routes/entry'}}, 'listeners'
    )
    assert client.get(sock_type='ipv6')['status'] == 404
    assert 'success' in client.conf(
        [{'action': {'return': 200}}], 'routes/::1'
    )
    assert client.get(sock_type='ipv6')['status'] == 200

def test_variables_time_local(require):
    require({'modules': {'njs': 'any'}})
    set_condition(
        '`${Math.abs(Date.parse(vars.time_local.replace('
        '"/", " ").replace("/", " ").replace(":", " ")) '
        '- Date.now()) < 5000}`'
    )
    assert client.get()['status'] == 200

@pytest.mark.parametrize('target', ['/r_line', '/a%2Fb?arg=a%2Bb', '/path?'])
def test_variables_request_line(require, target):
    require({'modules': {'njs': 'any'}})
    expected = json.dumps(f'GET {target} HTTP/1.1')
    set_condition('`${vars.request_line === ' + expected + '}`')
    assert client.get(url=target)['status'] == 200
    assert client.post(url=target)['status'] == 404

def test_variables_request_id(require):
    require({'modules': {'njs': 'any'}})
    assert 'success' in client.conf(
        {
            'listeners': {'*:8080': {'pass': 'routes/entry'}},
            'routes': {
                'entry': [
                    {
                        'match': {'if': '$request_id'},
                        'action': {'pass': 'routes/check'},
                    }
                ],
                'check': [
                    {
                        'match': {
                            'if': '`${/^[0-9a-f]{32}$/.test(vars.request_id) '
                                  '&& vars.request_id === vars.request_id}`'
                        },
                        'action': {'return': 200},
                    }
                ],
            },
        }
    ), 'configure cached request ID'
    assert client.get()['status'] == 200
    assert client.get()['status'] == 200

@pytest.mark.parametrize('name', ['header_referer', 'header_user_agent'])
@pytest.mark.parametrize('value', ['referer-value', '', 'no'])
def test_variables_known_headers(name, value):
    set_variable('routes/value${' + name + '}', 'value' + value)
    header = 'Referer' if name == 'header_referer' else 'User-Agent'
    assert client.get(headers={header: value, 'Connection': 'close'})[
        'status'
    ] == 200
    assert client.get(headers={header: 'different', 'Connection': 'close'})[
        'status'
    ] == 404

@pytest.mark.parametrize(
    'template, value',
    [
        ('routes$uri$method', '1GET'),
        ('routes${uri}${method}', '1GET'),
        ('routes${uri}$method', '1GET'),
        ('routes/$method$method', 'GETGET'),
    ],
)
def test_variables_many(template, value):
    set_variable(template, value)
    assert client.get(url='/1')['status'] == 200
    assert client.post(url='/1')['status'] == 404

def test_variables_empty():
    for prefix in ('routes', 'applications'):
        assert 'success' in client.conf(
            {'listeners': {'*:8080': {'pass': prefix + '/$method'}}},
        ), 'variables empty'
        assert client.get()['status'] == 404

@pytest.mark.parametrize('pass_value', ['upstreams/$method', '$arg_destination'])
def test_variables_upstreams_unsupported(pass_value):
    assert 'success' in client.conf(
        {'pass': pass_value}, 'listeners/*:8080'
    ), 'dynamic pass configure'
    assert client.get(url='/?destination=upstreams/one')['status'] == 404

    assert 'success' in client.conf({'pass': 'routes'}, 'listeners/*:8080')
    assert client.get()['status'] == 200

def test_variables_dynamic():
    set_variable('routes/$header_foo$cookie_foo$arg_foo', 'blah')
    assert client.get(
        url='/?foo=h',
        headers={'Foo': 'b', 'Cookie': 'foo=la', 'Connection': 'close'},
    )['status'] == 200
    assert client.get(url='/?foo=h')['status'] == 404

def test_variables_dynamic_arguments():
    set_variable('routes/value$arg_foo_bar', 'value')
    for url in ('/', '/?foo_bar=', '/?Foo_bar=0', '/?foo-bar=0'):
        assert client.get(url=url)['status'] == 200

    set_variable('routes/value$arg_foo_bar', 'value4')
    assert client.get(url='/?foo_bar=l&foo_bar=4')['status'] == 200
    assert client.get(url='/?foo_bar=4&foo_bar=l')['status'] == 404

    for url in ('/?foo_bar=4', '/?foo_b%61r=4', '/?bar&foo_bar=4&foo'):
        assert client.get(url=url)['status'] == 200

    set_variable('routes/value$arg_foo_b%61r', 'value0ar')
    assert client.get(url='/?foo_b=0')['status'] == 200
    assert client.get(url='/?foo_bar=0')['status'] == 404

    set_variable('routes/value$arg_foo_b%61r', 'valuear')
    assert client.get(url='/?foo_bar=0')['status'] == 200

    set_variable('routes/value$arg_f!~', 'value0!~')
    assert client.get(url='/?f=0')['status'] == 200
    assert client.get(url='/?f!~=0')['status'] == 404

    set_variable('routes/value$arg_f!~', 'value!~')
    assert client.get(url='/?f!~=0')['status'] == 200

@pytest.mark.parametrize('name', ['header_foo_bar', 'header_Foo_Bar'])
def test_variables_dynamic_headers(name):
    set_variable('routes/value${' + name + '}', 'value1')
    for header in ('foo-bar', 'Foo-Bar'):
        assert client.get(headers={header: '1', 'Connection': 'close'})[
            'status'
        ] == 200
    for header in ('foo_bar', 'foobar'):
        assert client.get(headers={header: '1', 'Connection': 'close'})[
            'status'
        ] == 404

    set_variable('routes/value${' + name + '}', 'value')
    assert client.get()['status'] == 200

def test_variables_dynamic_cookies():
    set_variable('routes/value$cookie_foo_bar', 'value1')
    assert client.get(headers={'Cookie': 'foo_bar=1', 'Connection': 'close'})[
        'status'
    ] == 200
    for cookie in ('fOo_bar=1', 'foo_bar='):
        assert client.get(headers={'Cookie': cookie, 'Connection': 'close'})[
            'status'
        ] == 404

    set_variable('routes/value$cookie_foo_bar', 'value')
    assert client.get()['status'] == 200

@pytest.mark.parametrize(
    'template',
    [
        '$', '${', '${}', '$ur', '$uri$$host', '$uriblah', '${uri',
        '${{uri}', '$ar', '$arg', '$arg_', '$cookie', '$cookie_',
        '$header', '$header_',
    ],
)
def test_variables_invalid(template):
    before = client.conf_get()
    assert 'error' in client.conf(
        {'pass': template}, 'routes/0/action'
    ), 'invalid variable'
    assert client.conf_get() == before
    assert client.get()['status'] == 200

@pytest.mark.parametrize(
    'variable',
    [
        'status', 'body_bytes_sent', 'response_header_server',
        'response_header_connection', 'response_header_content_length',
        'response_header_transfer_encoding',
    ],
)
def test_variables_response_unsupported(variable):
    before = client.conf_get()
    result = client.conf({'pass': '$' + variable}, 'routes/0/action')
    assert 'error' in result
    assert 'Unknown variable' in result['detail']
    assert client.conf_get() == before
    assert client.get()['status'] == 200
