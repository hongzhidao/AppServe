from unit.applications.lang.python import ApplicationPython
from unit.option import option

prerequisites = {'modules': {'njs': 'any', 'python': 'any'}}

client = ApplicationPython()


def njs_script_load(module, name=None, expect='success'):
    if name is None:
        name = module

    with open(f'{option.test_dir}/njs/{module}/script.js', 'rb') as script:
        assert expect in client.conf(script.read(), f'/js_modules/{name}')


def test_njs_modules():
    client.load('empty', name='next')
    njs_script_load('next')

    assert 'export' in client.conf_get('/js_modules/next')
    assert 'error' in client.conf_post('"blah"', '/js_modules/next')

    assert 'success' in client.conf({'js_module': 'next'}, 'settings')
    assert 'success' in client.conf(
        {'pass': '`applications/${next.route()}`'}, 'listeners/*:8080'
    )
    assert client.get()['status'] == 200, 'string'

    assert 'success' in client.conf({"js_module": ["next"]}, 'settings')
    assert client.get()['status'] == 200, 'array'

    # add one more value to array

    assert len(client.conf_get('/js_modules').keys()) == 1

    njs_script_load('next', 'next_2')

    assert len(client.conf_get('/js_modules').keys()) == 2

    assert 'success' in client.conf_post('"next_2"', 'settings/js_module')
    assert client.get()['status'] == 200, 'array len 2'

    assert 'success' in client.conf(
        '"`applications/${next_2.route()}`"', 'listeners/*:8080/pass'
    )
    assert client.get()['status'] == 200, 'array new'

    # can't update exsisting script

    njs_script_load('global_this', 'next', expect='error')

    # delete modules

    assert 'error' in client.conf_delete('/js_modules/next_2')
    assert 'success' in client.conf_delete('settings/js_module')
    assert 'success' in client.conf_delete('/js_modules/next_2')


def test_njs_modules_import():
    client.load('empty', name='number')
    njs_script_load('import_from')

    assert 'success' in client.conf({'js_module': 'import_from'}, 'settings')
    assert 'success' in client.conf(
        {'pass': '`applications/${import_from.num()}`'}, 'listeners/*:8080'
    )
    assert client.get()['status'] == 200


def test_njs_modules_this():
    client.load('empty', name='string')
    njs_script_load('global_this')

    assert 'success' in client.conf({'js_module': 'global_this'}, 'settings')
    assert 'success' in client.conf(
        {'pass': '`applications/${global_this.str()}`'}, 'listeners/*:8080'
    )
    assert client.get()['status'] == 200


def test_njs_modules_invalid(skip_alert):
    skip_alert(r'.*JS compile module.*failed.*')

    njs_script_load('invalid', expect='error')
