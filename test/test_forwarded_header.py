import json
import socket

import pytest
from unit.applications.lang.python import ApplicationPython
from unit.applications.websockets import ApplicationWebsocket

prerequisites = {'modules': {'python': 'any'}}

client = ApplicationPython()


@pytest.fixture(autouse=True)
def setup_method_fixture():
    client.load('forwarded_header')


def configure(trusted=None):
    listener = {'pass': 'applications/forwarded_header'}
    if trusted is not None:
        listener['forwarded'] = {'trusted': trusted}

    assert 'success' in client.conf(
        {'127.0.0.1:8091': listener, '[::1]:8092': listener}, 'listeners'
    )


def get_forwarded(value=None, sock_type='ipv4', **kwargs):
    headers = {'Host': 'localhost', 'Connection': 'close'}
    if value is not None:
        headers['Forwarded'] = value
    headers.update(kwargs.pop('headers', {}))

    return client.get(
        port=8091 if sock_type == 'ipv4' else 8092,
        sock_type=sock_type,
        headers=headers,
        **kwargs,
    )


def assert_metadata(response, address, scheme='http'):
    assert response['status'] == 200
    assert response['headers']['Remote-Addr'] == address
    assert response['headers']['Url-Scheme'] == scheme


@pytest.mark.parametrize('trusted', [None, [], '192.0.2.1'])
def test_forwarded_untrusted(trusted):
    configure(trusted)
    assert_metadata(get_forwarded('for=203.0.113.9;proto=https'), '127.0.0.1')
    assert_metadata(
        get_forwarded('for=203.0.113.9;proto=https', 'ipv6'), '::1'
    )


@pytest.mark.parametrize(
    'trusted, ipv4, ipv6',
    [
        ('127.0.0.1', True, False),
        ('127.0.0.0/8', True, False),
        ('::1', False, True),
        ('::/127', False, True),
        (['127.0.0.1', '::1'], True, True),
        (['0.0.0.0/0', '::/0'], True, True),
    ],
)
def test_forwarded_trusted(trusted, ipv4, ipv6):
    configure(trusted)
    value = 'for=203.0.113.9;proto=https'
    assert_metadata(
        get_forwarded(value),
        '203.0.113.9' if ipv4 else '127.0.0.1',
        'https' if ipv4 else 'http',
    )
    assert_metadata(
        get_forwarded(value, 'ipv6'),
        '203.0.113.9' if ipv6 else '::1',
        'https' if ipv6 else 'http',
    )


@pytest.mark.parametrize(
    'value, address, scheme',
    [
        (None, '127.0.0.1', 'http'),
        ('for=203.0.113.9', '203.0.113.9', 'http'),
        ('proto=https', '127.0.0.1', 'https'),
        ('for=203.0.113.9;proto=HTTPS', '203.0.113.9', 'https'),
        ('for="203.0.113.9:443";proto="https"', '203.0.113.9', 'https'),
        ('for="203.0.113.9:0";proto=http', '203.0.113.9', 'http'),
        ('for="203.0.113.9:_hidden";proto=https', '203.0.113.9', 'https'),
        ('for="[2001:db8::1]";proto=https', '2001:db8::1', 'https'),
        ('for="[2001:db8::1]:443"', '2001:db8::1', 'http'),
        ('for="[::ffff:192.0.2.1]"', '::ffff:192.0.2.1', 'http'),
        ('for="203.0.113.\\9";proto="h\\ttps"', '203.0.113.9', 'https'),
        ('\tFor=203.0.113.9;\tPROTO=https\t', '203.0.113.9', 'https'),
        (';for=203.0.113.9;;proto=https;', '203.0.113.9', 'https'),
        ('for=203.0.113.9;proto=on', '203.0.113.9', 'http'),
        ('for=203.0.113.9;proto="http,https"', '203.0.113.9', 'http'),
        ('for=unknown;proto=https', '127.0.0.1', 'https'),
        ('for="unknown:443";proto=https', '127.0.0.1', 'https'),
        ('for=_hidden;proto=https', '127.0.0.1', 'https'),
        ('for="_hidden:_port";proto=https', '127.0.0.1', 'https'),
        (
            'for=203.0.113.9;proto=https;host="external.example:443";'
            'by=_proxy;ext="a,b;c=\\\"quoted\\\""',
            '203.0.113.9',
            'https',
        ),
    ],
)
def test_forwarded_values(value, address, scheme):
    configure('127.0.0.1')
    assert_metadata(get_forwarded(value), address, scheme)


@pytest.mark.parametrize(
    'value',
    [
        '',
        ' ',
        ';',
        'for=',
        'for="";proto=https',
        'for=203.0.113.9;proto=',
        'for=203.0.113.9;FOR=198.51.100.7',
        'for=203.0.113.9;proto=http;Proto=https',
        'for=203.0.113.9;ext=a;EXT=b',
        'for=203.0.113.9;host=a;host=b',
        'for=203.0.113.9;by=a;BY=b',
        'for=203.0.113.9;broken',
        'for =203.0.113.9',
        'for= 203.0.113.9',
        'for=203.0.113.9 proto=https',
        'for="203.0.113.9',
        'for="203.0.113.9\\',
        'for="203.0.113.9"junk',
        'for=203.0.113.9,',
        'for=example.com;proto=https',
        'for=203.0.113.999;proto=https',
        'for=203.000.113.9;proto=https',
        'for=0.0.0.0;proto=https',
        'for="[::]";proto=https',
        'for=2001:db8::1;proto=https',
        'for="2001:db8::1";proto=https',
        'for=[2001:db8::1];proto=https',
        'for="[2001:db8::1";proto=https',
        'for="[2001:db8::1]extra";proto=https',
        'for="[fe80::1%lo]";proto=https',
        'for=203.0.113.9:443;proto=https',
        'for="203.0.113.9:";proto=https',
        'for="203.0.113.9:65536";proto=https',
        'for="203.0.113.9:123456";proto=https',
        'for="203.0.113.9:-1";proto=https',
        'for="203.0.113.9:_";proto=https',
        'for="203.0.113.9:_!";proto=https',
        'for=_;proto=https',
        'for=_bad!;proto=https',
    ],
)
def test_forwarded_invalid(value):
    configure('127.0.0.1')
    assert_metadata(get_forwarded(value), '127.0.0.1')


@pytest.mark.parametrize(
    'value, address, scheme',
    [
        (
            'for=203.0.113.9;proto=https, for=10.20.0.2;proto=http',
            '203.0.113.9',
            'https',
        ),
        (
            'for=192.0.2.1;proto=https, for=198.51.100.7;proto=http, '
            'for=10.20.0.2;proto=https',
            '198.51.100.7',
            'http',
        ),
        (
            'for=10.20.0.1;proto=https, for=10.20.0.2;proto=http',
            '10.20.0.1',
            'https',
        ),
        (
            ['for=203.0.113.9;proto=https', 'for=10.20.0.2;proto=http'],
            '203.0.113.9',
            'https',
        ),
        (
            ['for=192.0.2.1', 'for=198.51.100.7;proto=https', 'for=10.20.0.2'],
            '198.51.100.7',
            'https',
        ),
        (
            'for=invalid;proto=https, for=198.51.100.7;proto=http',
            '198.51.100.7',
            'http',
        ),
        (
            'garbage, for=198.51.100.7;proto=https',
            '198.51.100.7',
            'https',
        ),
        ('for=203.0.113.9, for=invalid;proto=https', '127.0.0.1', 'http'),
        ('for=invalid, for=10.20.0.2;proto=https', '127.0.0.1', 'http'),
        ('for=203.0.113.9, for=unknown;proto=https', '127.0.0.1', 'https'),
        ('for=203.0.113.9, proto=https', '127.0.0.1', 'https'),
        ('for=203.0.113.9, , for=10.20.0.2', '127.0.0.1', 'http'),
        (['for=203.0.113.9', ''], '127.0.0.1', 'http'),
        (
            'for=203.0.113.9, for="[::ffff:10.20.0.2]"',
            '203.0.113.9',
            'http',
        ),
        ('for=203.0.113.9, for="[2001:db8::2]"', '203.0.113.9', 'http'),
        (
            'for=203.0.113.9, for=10.20.0.2;proto=https',
            '203.0.113.9',
            'http',
        ),
    ],
)
def test_forwarded_chain(value, address, scheme):
    configure(['127.0.0.1', '10.20.0.0/16', '2001:db8::/32'])
    assert_metadata(get_forwarded(value), address, scheme)


def test_forwarded_case_and_original_headers():
    configure('127.0.0.1')
    value = 'For=203.0.113.9;Proto=https;host=external.example'
    response = get_forwarded(headers={'fOrWaRdEd': value})
    assert_metadata(response, '203.0.113.9', 'https')
    assert response['headers']['Forwarded-Value'] == value
    assert response['headers']['Request-Host'] == 'localhost'


def test_forwarded_x_headers():
    configure('127.0.0.1')
    headers = {'X-Forwarded-For': '192.0.2.1', 'X-Forwarded-Proto': 'https'}
    assert_metadata(get_forwarded(headers=headers), '127.0.0.1')
    assert_metadata(
        get_forwarded('for=203.0.113.9;proto=http', headers=headers),
        '203.0.113.9',
    )


def test_forwarded_mapped_trusted_address():
    configure(['127.0.0.1', '::ffff:10.20.0.2/128'])
    assert_metadata(
        get_forwarded('for=203.0.113.9;proto=https, for="[::ffff:10.20.0.2]"'),
        '203.0.113.9',
        'https',
    )


def test_forwarded_unix_peer(temp_dir):
    addr = f'{temp_dir}/forwarded.sock'
    listener = {
        'pass': 'applications/forwarded_header',
        'forwarded': {'trusted': ['0.0.0.0/0', '::/0']},
    }
    assert 'success' in client.conf({'unix:' + addr: listener}, 'listeners')
    response = get_forwarded('for=203.0.113.9;proto=https', 'unix', addr=addr)
    assert response['status'] == 200
    assert response['headers']['Remote-Addr'] != '203.0.113.9'
    assert response['headers']['Url-Scheme'] == 'http'


@pytest.mark.parametrize('scheme', ['http', 'https'])
def test_forwarded_asgi(scheme):
    client.load('forwarded_header', module='asgi', protocol='asgi')
    configure('127.0.0.1')
    response = get_forwarded(f'for=203.0.113.9;proto={scheme}')
    assert response['status'] == 200
    assert json.loads(response['body']) == {
        'client': '203.0.113.9', 'scheme': scheme
    }


@pytest.mark.parametrize('scheme', ['http', 'https'])
def test_forwarded_websocket(scheme):
    client.load('forwarded_header', module='asgi', protocol='asgi')
    configure('127.0.0.1')
    ws = ApplicationWebsocket()
    headers = {
        'Host': 'localhost',
        'Connection': 'Upgrade',
        'Upgrade': 'websocket',
        'Sec-WebSocket-Key': ws.key(),
        'Sec-WebSocket-Version': '13',
        'Forwarded': f'for=203.0.113.9;proto={scheme}',
    }
    sock = socket.create_connection(('127.0.0.1', 8091))
    try:
        get_forwarded(sock=sock, headers=headers, no_recv=True)
        sock.settimeout(5)
        response = b''
        while not response.endswith(b'\r\n\r\n'):
            part = sock.recv(1)
            assert part, 'incomplete websocket handshake'
            response += part
        response = client._resp_to_dict(response.decode())
        assert response['status'] == 101
        metadata = json.loads(ws.frame_read(sock)['data'])
        assert metadata == {
            'client': '203.0.113.9',
            'scheme': 'wss' if scheme == 'https' else 'ws',
        }
        assert ws.frame_read(sock)['opcode'] == ws.OP_CLOSE
    finally:
        sock.close()


def test_forwarded_keepalive_and_reconfigure():
    configure('127.0.0.1')
    response, sock = get_forwarded(
        'for=203.0.113.9;proto=https',
        headers={'Connection': 'keep-alive'},
        start=True,
        read_timeout=0.1,
    )
    try:
        assert_metadata(response, '203.0.113.9', 'https')
        response, _ = get_forwarded(
            sock=sock,
            start=True,
            headers={'Connection': 'keep-alive'},
            read_timeout=0.1,
        )
        assert_metadata(response, '127.0.0.1')
        configure([])
        assert_metadata(
            get_forwarded('for=192.0.2.1;proto=https', sock=sock), '127.0.0.1'
        )
    finally:
        sock.close()


@pytest.mark.parametrize(
    'trusted',
    [
        None, True, 1, {}, ['127.0.0.1', None], ['127.0.0.1', 1],
        '', 'hostname', '!127.0.0.1', '*:0-65535', '127.0.0.1:443',
        '127.0.0.0-127.0.0.1', '[::1]:443', '::-::1', 'unix:/tmp/proxy',
        '127.0.0.1/33', '::1/129', 'invalid/0', '127.0.0.1/24/1',
        '127.0.0.1\x00junk',
    ],
)
def test_forwarded_invalid_trusted(trusted):
    listener = {
        'pass': 'applications/forwarded_header',
        'forwarded': {'trusted': trusted},
    }
    assert 'error' in client.conf({'127.0.0.1:8091': listener}, 'listeners')


@pytest.mark.parametrize(
    'options',
    [
        {'forwarded': {}},
        {'client_ip': {}},
        {'client_ip': {'source': '127.0.0.1', 'header': 'X-Forwarded-For'}},
        {'forwarded': {'source': '127.0.0.1', 'client_ip': 'X-Forwarded-For'}},
        {'forwarded': {'trusted': [], 'source': '127.0.0.1'}},
        {'forwarded': {'trusted': [], 'client_ip': 'X-Forwarded-For'}},
        {'forwarded': {'trusted': [], 'protocol': 'X-Forwarded-Proto'}},
        {'forwarded': {'trusted': [], 'recursive': True}},
    ],
)
def test_forwarded_removed_options(options):
    listener = {'pass': 'applications/forwarded_header', **options}
    assert 'error' in client.conf({'127.0.0.1:8091': listener}, 'listeners')
