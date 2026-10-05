import json

import pytest
from unit.applications.lang.python import ApplicationPython

prerequisites = {'modules': {'python': 'any'}}

client = ApplicationPython()


@pytest.fixture(autouse=True)
def setup_method_fixture():
    client.load('empty')


@pytest.mark.parametrize(
    'routes',
    [
        [],
        {},
        [{'action': {'return': 200}}],
        {'main': [{'match': {'uri': '/'}, 'action': {'return': 200}}]},
    ],
)
@pytest.mark.parametrize('path', ['', 'routes'])
def test_routes_unsupported(routes, path):
    before = client.conf_get()
    conf = {**before, 'routes': routes} if path == '' else routes

    result = client.conf(conf, path)

    assert 'error' in result
    assert result['detail'] == 'Unknown parameter "routes".'
    assert client.conf_get() == before
    assert client.get()['status'] == 200


@pytest.mark.parametrize('path', ['routes/main', 'routes/0/action/return'])
def test_routes_nested_update_unsupported(path):
    before = client.conf_get()

    assert 'error' in client.conf({'return': 200}, path)
    assert client.conf_get() == before
    assert client.get()['status'] == 200


@pytest.mark.parametrize(
    'value', ['routes', 'routes/main', 'r%6Futes/main', 'upstreams/one']
)
def test_pass_unsupported_destination(value):
    before = client.conf_get()

    result = client.conf({'pass': value}, 'listeners/*:8080')

    assert 'error' in result
    assert result['detail'] == (
        f'Request "pass" points to invalid location "{value}".'
    )
    assert client.conf_get() == before
    assert client.get()['status'] == 200


@pytest.mark.parametrize(
    'parameter, value',
    [
        ('return', 200),
        ('location', '/new'),
        ('action', {'return': 200}),
        ('match', {'uri': '/'}),
        ('proxy', 'http://127.0.0.1:8081'),
        ('share', '/app$uri'),
        ('rewrite', '/new'),
        ('response_headers', {'X-Foo': 'foo'}),
    ],
)
def test_listener_route_options_unsupported(parameter, value):
    before = client.conf_get()

    result = client.conf(json.dumps(value), 'listeners/*:8080/' + parameter)

    assert 'error' in result
    assert result['detail'] == f'Unknown parameter "{parameter}".'
    assert client.conf_get() == before
    assert client.get()['status'] == 200


@pytest.mark.parametrize(
    'name', ['%', 'blah/blah', '/blah//blah/', ' blah%2Fblah~', '$method', '`app`']
)
def test_pass_application_encoded(name):
    client.load('empty', name=name)
    assert client.get()['status'] == 200


@pytest.mark.parametrize(
    'value',
    ['applications/%', 'applications/%1', 'applications',
     'applications/missing', 'applications/empty/missing',
     'applications/empty/target/extra'],
)
def test_pass_application_invalid(value):
    before = client.conf_get()

    assert 'error' in client.conf({'pass': value}, 'listeners/*:8080')
    assert client.conf_get() == before
    assert client.get()['status'] == 200


def test_listener_application_compatibility():
    assert 'success' in client.conf({'application': 'empty'}, 'listeners/*:8080')
    assert client.get()['status'] == 200


def test_pass_application_update():
    app = client.conf_get('applications/empty')
    assert 'success' in client.conf(app, 'applications/second')
    assert 'success' in client.conf(
        {'pass': 'applications/second'}, 'listeners/*:8080'
    )
    assert 'success' in client.conf_delete('applications/empty')
    assert client.get()['status'] == 200


@pytest.mark.parametrize(
    'value',
    [
        '$arg_pass',
        'applications/$method',
        'applications/${host}',
        'applications/empty/$arg_target',
        'applications/empty${uri}',
        '`applications/${host}`',
        '`applications/empty`',
    ],
)
@pytest.mark.parametrize('path', ['listeners/*:8080', 'listeners/*:8080/pass'])
def test_pass_dynamic_unsupported(value, path):
    before = client.conf_get()
    conf = json.dumps(value) if path.endswith('/pass') else {'pass': value}

    result = client.conf(conf, path)

    assert 'error' in result
    assert result['detail'] == (
        'The "pass" value must be a fixed application destination.'
    )
    assert client.conf_get() == before
    assert client.get()['status'] == 200


def test_pass_target_update():
    app = client.conf_get('applications/empty')
    del app['module']
    app['targets'] = {'first': {'module': 'wsgi'}, 'second': {'module': 'wsgi'}}
    assert 'success' in client.conf(app, 'applications/empty')
    assert 'success' in client.conf(
        {'pass': 'applications/empty/first'}, 'listeners/*:8080'
    )

    before = client.conf_get()
    assert 'error' in client.conf(
        {'pass': 'applications/empty/missing'}, 'listeners/*:8080'
    )
    assert client.conf_get() == before
    assert client.get()['status'] == 200

    assert 'success' in client.conf(
        {'pass': 'applications/empty/second'}, 'listeners/*:8080'
    )
    assert client.get()['status'] == 200

    assert 'error' in client.conf_delete('applications/empty/targets/second')
    assert 'success' in client.conf(
        {'pass': 'applications/empty/first'}, 'listeners/*:8080'
    )

    assert 'success' in client.conf_delete('applications/empty/targets/second')
    assert client.get()['status'] == 200
