import json
import socket

import pytest
from unit.control import Control
from unit.option import option

prerequisites = {'modules': {'python': 'any'}}


client = Control()


def try_addr(addr):
    return client.conf(
        {
            "listeners": {addr: {"pass": "applications/empty"}},
            "applications": {
                "empty": {
                    "type": "python",
                    "processes": {"spare": 0},
                    "path": option.test_dir + '/python/empty',
                    "module": "wsgi",
                }
            },
        }
    )

@pytest.mark.parametrize('static', [{}, {'mime_types': {'text/plain': ['txt']}}])
def test_http_static_unsupported(static):
    assert 'success' in try_addr('*:8080')
    assert 'success' in client.conf({'http': {}}, 'settings')
    before = client.conf_get()

    result = client.conf(static, 'settings/http/static')

    assert 'error' in result, 'unsupported static settings'
    assert result['detail'] == 'Unknown parameter "static".'
    assert client.conf_get() == before, 'configuration unchanged'
    assert client.get()['status'] == 200, 'original route still works'

@pytest.mark.parametrize(
    'upstreams',
    [{}, {'one': {'servers': {'127.0.0.1:8081': {'weight': 2}}}}],
)
@pytest.mark.parametrize('path', ['', 'upstreams'])
def test_upstreams_unsupported(upstreams, path):
    assert 'success' in try_addr('*:8080')
    before = client.conf_get()

    conf = {**before, 'upstreams': upstreams} if path == '' else upstreams
    result = client.conf(conf, path)

    assert 'error' in result, 'unsupported upstreams configuration'
    assert result['detail'] == 'Unknown parameter "upstreams".'
    assert client.conf_get() == before, 'configuration unchanged'
    assert client.get()['status'] == 200, 'original route still works'

@pytest.mark.parametrize(
    'access_log',
    [
        '/access.log',
        {},
        {'path': '/access.log'},
        {'path': '/access.log', 'format': '$request_line $status'},
        {'path': '/access.log', 'format': {'uri': '$uri', 'status': '$status'}},
        {'path': '/access.log', 'if': '$arg_log'},
    ],
)
@pytest.mark.parametrize('path', ['', 'access_log'])
def test_access_log_unsupported(access_log, path):
    assert 'success' in try_addr('*:8080')
    before = client.conf_get()

    conf = {**before, 'access_log': access_log} if path == '' else access_log
    result = client.conf(json.dumps(conf), path)

    assert 'error' in result, 'unsupported access_log configuration'
    assert result['detail'] == 'Unknown parameter "access_log".'
    assert client.conf_get() == before, 'configuration unchanged'
    assert client.get()['status'] == 200, 'original route still works'

@pytest.mark.parametrize('js_module', ['next', ['next'], []])
def test_js_module_unsupported(js_module):
    assert 'success' in try_addr('*:8080')
    assert 'success' in client.conf({}, 'settings')
    before = client.conf_get()

    result = client.conf(json.dumps(js_module), 'settings/js_module')

    assert 'error' in result, 'unsupported js_module configuration'
    assert result['detail'] == 'Unknown parameter "js_module".'
    assert client.conf_get() == before
    assert client.get()['status'] == 200

@pytest.mark.parametrize('method', ['GET', 'PUT', 'DELETE'])
@pytest.mark.parametrize('path', ['/js_modules', '/js_modules/next'])
def test_js_modules_api_unsupported(method, path):
    assert 'success' in try_addr('*:8080')
    before = client.conf_get()

    result = client.http(
        method,
        url=path,
        sock_type='unix',
        addr=option.temp_dir + '/control.appserve.sock',
        body='export default {}; ' if method == 'PUT' else '',
    )

    assert result['status'] == 404
    assert 'js_modules' not in client.conf_get('/')
    assert client.conf_get() == before
    assert client.get()['status'] == 200

def test_json_empty():
    assert 'error' in client.conf(''), 'empty'

def test_json_leading_zero():
    assert 'error' in client.conf('00'), 'leading zero'

def test_json_unicode():
    assert 'success' in client.conf(
        """
        {
            "ap\u0070": {
                "type": "\u0070ython",
                "processes": { "spare": 0 },
                "path": "\u002Fapp",
                "module": "wsgi"
            }
        }
        """,
        'applications',
    ), 'unicode'

    assert client.conf_get('applications') == {
        "app": {
            "type": "python",
            "processes": {"spare": 0},
            "path": "/app",
            "module": "wsgi",
        }
    }, 'unicode get'

def test_json_unicode_2():
    assert 'success' in client.conf(
        {
            "приложение": {
                "type": "python",
                "processes": {"spare": 0},
                "path": "/app",
                "module": "wsgi",
            }
        },
        'applications',
    ), 'unicode 2'

    assert 'приложение' in client.conf_get('applications'), 'unicode 2 get'

def test_json_unicode_number():
    assert 'success' in client.conf(
        """
        {
            "app": {
                "type": "python",
                "processes": { "spare": \u0030 },
                "path": "/app",
                "module": "wsgi"
            }
        }
        """,
        'applications',
    ), 'unicode number'

def test_json_utf8_bom():
    assert 'success' in client.conf(
        b"""\xEF\xBB\xBF
        {
            "app": {
                "type": "python",
                "processes": {"spare": 0},
                "path": "/app",
                "module": "wsgi"
            }
        }
        """,
        'applications',
    ), 'UTF-8 BOM'

def test_json_comment_single_line():
    assert 'success' in client.conf(
        b"""
        // this is bridge
        {
            "//app": {
                "type": "python", // end line
                "processes": {"spare": 0},
                // inside of block
                "path": "/app",
                "module": "wsgi"
            }
            // double //
        }
        // end of json \xEF\t
        """,
        'applications',
    ), 'single line comments'

def test_json_comment_multi_line():
    assert 'success' in client.conf(
        b"""
        /* this is bridge */
        {
            "/*app": {
            /**
             * multiple lines
             **/
                "type": "python",
                "processes": /* inline */ {"spare": 0},
                "path": "/app",
                "module": "wsgi"
                /*
                // end of block */
            }
            /* blah * / blah /* blah */
        }
        /* end of json \xEF\t\b */
        """,
        'applications',
    ), 'multi line comments'

def test_json_comment_invalid():
    assert 'error' in client.conf(b'/{}', 'applications'), 'slash'
    assert 'error' in client.conf(b'//{}', 'applications'), 'comment'
    assert 'error' in client.conf(b'{} /', 'applications'), 'slash end'
    assert 'error' in client.conf(b'/*{}', 'applications'), 'slash star'
    assert 'error' in client.conf(b'{} /*', 'applications'), 'slash star end'

def test_applications_open_brace():
    assert 'error' in client.conf('{', 'applications'), 'open brace'

def test_applications_string():
    assert 'error' in client.conf('"{}"', 'applications'), 'string'

@pytest.mark.skip('not yet, unsafe')
def test_applications_type_only():
    assert 'error' in client.conf(
        {"app": {"type": "python"}}, 'applications'
    ), 'type only'

def test_applications_unknown_type():
    before = client.conf_get()

    result = client.conf(
        {
            "app": {
                "type": "unknown",
                "processes": {"spare": 0},
            }
        },
        'applications',
    )

    assert 'error' in result, 'unknown application type'
    assert 'not found' in result['detail'], 'unavailable application module'
    assert client.conf_get() == before, 'configuration unchanged'

def test_applications_miss_quote():
    assert 'error' in client.conf(
        """
        {
            app": {
                "type": "python",
                "processes": { "spare": 0 },
                "path": "/app",
                "module": "wsgi"
            }
        }
        """,
        'applications',
    ), 'miss quote'

def test_applications_miss_colon():
    assert 'error' in client.conf(
        """
        {
            "app" {
                "type": "python",
                "processes": { "spare": 0 },
                "path": "/app",
                "module": "wsgi"
            }
        }
        """,
        'applications',
    ), 'miss colon'

def test_applications_miss_comma():
    assert 'error' in client.conf(
        """
        {
            "app": {
                "type": "python"
                "processes": { "spare": 0 },
                "path": "/app",
                "module": "wsgi"
            }
        }
        """,
        'applications',
    ), 'miss comma'

def test_applications_skip_spaces():
    assert 'success' in client.conf(
        b'{ \n\r\t}', 'applications'
    ), 'skip spaces'

def test_applications_relative_path():
    assert 'success' in client.conf(
        {
            "app": {
                "type": "python",
                "processes": {"spare": 0},
                "path": "../app",
                "module": "wsgi",
            }
        },
        'applications',
    ), 'relative path'

@pytest.mark.parametrize('tls', [{}, {'certificate': 'bundle'}])
def test_listeners_tls_unsupported(tls):
    assert 'success' in try_addr('*:8080')
    before = client.conf_get()

    result = client.conf(
        {'*:8080': {'pass': 'applications/empty', 'tls': tls}}, 'listeners'
    )

    assert 'error' in result, 'unsupported TLS listener'
    assert result['detail'] == 'Unknown parameter "tls".'
    assert client.conf_get() == before, 'configuration unchanged'
    assert client.get()['status'] == 200, 'HTTP listener still works'

@pytest.mark.parametrize('path', ['/certificates', '/certificates/bundle'])
@pytest.mark.parametrize('method', ['GET', 'PUT', 'DELETE'])
def test_certificates_api_removed(method, path):
    args = client._get_args(path, 'bundle' if method == 'PUT' else None)

    assert client.http(method, **args)['status'] == 404
    assert 'certificates' not in client.conf_get('/')

@pytest.mark.skip('not yet, unsafe')
def test_listeners_empty():
    assert 'error' in client.conf(
        {"*:8080": {}}, 'listeners'
    ), 'listener empty'

def test_listeners_no_app():
    assert 'error' in client.conf(
        {"*:8080": {"pass": "applications/app"}}, 'listeners'
    ), 'listeners no app'

def test_listeners_addr():
    assert 'success' in try_addr("*:8080"), 'wildcard'
    assert 'success' in try_addr("127.0.0.1:8081"), 'explicit'
    assert 'success' in try_addr("[::1]:8082"), 'explicit ipv6'

def test_listeners_addr_error():
    assert 'error' in try_addr("127.0.0.1"), 'no port'

def test_listeners_addr_error_2(skip_alert):
    skip_alert(r'bind.*failed', r'failed to apply new conf')

    assert 'error' in try_addr(
        "[f607:7403:1e4b:6c66:33b2:843f:2517:da27]:8080"
    )

def test_listeners_port_release():
    for _ in range(10):
        fail = False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            assert 'success' in try_addr('127.0.0.1:8080')

            resp = client.conf({"listeners": {}, "applications": {}})

            try:
                s.bind(('127.0.0.1', 8080))
                s.listen()

            except OSError:
                fail = True

            if fail:
                pytest.fail('cannot bind or listen to the address')

            assert 'success' in resp, 'port release'

def test_json_application_name_large():
    name = "X" * 1024 * 1024

    assert 'success' in client.conf(
        {
            "listeners": {"*:8080": {"pass": "applications/" + name}},
            "applications": {
                name: {
                    "type": "python",
                    "processes": {"spare": 0},
                    "path": "/app",
                    "module": "wsgi",
                }
            },
        }
    )

@pytest.mark.skip('not yet')
def test_json_application_many():
    apps = 999

    conf = {
        "applications": {
            "app-"
            + str(a): {
                "type": "python",
                "processes": {"spare": 0},
                "path": "/app",
                "module": "wsgi",
            }
            for a in range(apps)
        },
        "listeners": {
            "*:" + str(7000 + a): {"pass": "applications/app-" + str(a)}
            for a in range(apps)
        },
    }

    assert 'success' in client.conf(conf)

def test_json_application_many2():
    conf = {
        "applications": {
            "app-"
            + str(a): {
                "type": "python",
                "processes": {"spare": 0},
                "path": "/app",
                "module": "wsgi",
            }
            # Larger number of applications can cause test fail with default
            # open files limit due to the lack of file descriptors.
            for a in range(100)
        },
        "listeners": {"*:8080": {"pass": "applications/app-1"}},
    }

    assert 'success' in client.conf(conf)

def test_unprivileged_user_error(require, skip_alert):
    require({'privileged_user': False})

    skip_alert(r'cannot set user "root"', r'failed to apply new conf')

    assert 'error' in client.conf(
        {
            "app": {
                "type": "external",
                "processes": 1,
                "executable": "/app",
                "user": "root",
            }
        },
        'applications',
    ), 'setting user'
