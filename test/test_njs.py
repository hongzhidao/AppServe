import json
from urllib.parse import quote

import pytest
from unit.applications.lang.python import ApplicationPython

prerequisites = {'modules': {'njs': 'any', 'python': 'any'}}


client = ApplicationPython()


@pytest.fixture(autouse=True)
def setup_method_fixture():
    client.load('empty')

def create_applications(*names):
    app = client.conf_get('applications/empty')
    for name in names:
        assert 'success' in client.conf(
            app, f'applications/{quote(name, safe="")}'
        )

def set_pass(template):
    assert 'success' in client.conf(
        json.dumps(template), 'listeners/*:8080/pass'
    )

def check_expression(expression, url='/'):
    set_pass('`applications' + expression + '`')
    assert client.get(url=url)['status'] == 200

def test_njs_template_string():
    create_applications('str', '`string`', '`backtick', 'l1\nl2')

    check_expression('/str')
    check_expression('/\\`backtick')
    check_expression('/l1\\nl2')

    set_pass('applications/`string`')
    assert client.get()['status'] == 200

def test_njs_template_expression():
    create_applications('str', 'localhost')

    check_expression('${uri}', '/str')
    check_expression('${uri}${host}')
    check_expression('${uri + host}')
    check_expression('${uri + `${host}`}')

def test_njs_iteration():
    create_applications('Connection,Host', 'close,localhost')

    check_expression('/${Object.keys(headers).sort().join()}')
    check_expression('/${Object.values(headers).sort().join()}')

def test_njs_variables():
    create_applications('str', 'localhost', '127.0.0.1')

    check_expression('/${host}')
    check_expression('/${remoteAddr}')
    check_expression('/${headers.Host}')

    set_pass('`applications/${cookies.foo}`')
    assert (
        client.get(headers={'Cookie': 'foo=str', 'Connection': 'close'})[
            'status'
        ]
        == 200
    ), 'cookies'

    set_pass('`applications/${args.foo}`')
    assert client.get(url='/?foo=str')['status'] == 200, 'args'

    check_expression('/${vars.header_host}')
    check_expression('${vars.uri}', '/str')

    set_pass('`applications/${vars["arg_foo"]}`')
    assert client.get(url='/?foo=str')['status'] == 200, 'vars'

    set_pass('`applications/${vars.non_exist}`')
    assert client.get()['status'] == 404, 'undefined'

    create_applications('undefined')
    assert client.get()['status'] == 200, 'undefined 2'


def test_njs_variables_cacheable():
    create_applications('localhost-localhost', 'example.com-example.com')
    set_pass('`applications/${vars.host}-${vars.host}`')

    for _ in range(25):
        assert client.get()['status'] == 200
        assert client.get(
            headers={'Host': 'example.com', 'Connection': 'close'}
        )['status'] == 200


def test_njs_invalid(skip_alert):
    skip_alert(r'js exception:')

    def check_invalid(template):
        assert 'error' in client.conf(
            json.dumps(template), 'listeners/*:8080/pass'
        )

    check_invalid('`a')
    check_invalid('`a``')
    check_invalid('`a`/')
    check_invalid('`${vars.}`')

    def check_invalid_resolve(template):
        set_pass(template)
        assert client.get()['status'] == 500

    check_invalid_resolve('`${a}`')
    check_invalid_resolve('`${uri.a.a}`')
    check_invalid_resolve('`${vars.a.a}`')
