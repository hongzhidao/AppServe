from unit.applications.lang.ruby import ApplicationRuby
from unit.option import option
from unit.utils import waitforglob

prerequisites = {'modules': {'ruby': 'all'}}


client = ApplicationRuby()


def _wait_cookie(pattern, count):
    return waitforglob(
        option.temp_dir + '/ruby/hooks/cookie_' + pattern, count
    )

def test_ruby_hooks_eval():
    processes = 2

    client.load('hooks', processes=processes, hooks='eval.rb')

    hooked = _wait_cookie('eval.*', processes)

    assert hooked, 'hooks evaluated'

def test_ruby_hooks_on_worker_boot():
    processes = 2

    client.load('hooks', processes=processes, hooks='on_worker_boot.rb')

    hooked = _wait_cookie('worker_boot.*', processes)

    assert hooked, 'on_worker_boot called'

def test_ruby_hooks_on_worker_shutdown():
    processes = 2

    client.load('hooks', processes=processes, hooks='on_worker_shutdown.rb')

    assert client.get()['status'] == 200, 'app response'

    client.load('empty')

    hooked = _wait_cookie('worker_shutdown.*', processes)

    assert hooked, 'on_worker_shutdown called'

def test_ruby_hooks_multiple():
    processes = 2

    client.load(
        'hooks', processes=processes, hooks='multiple.rb',
    )

    hooked = _wait_cookie('worker_boot.*', processes)
    assert hooked, 'on_worker_boot called'

    assert client.get()['status'] == 200, 'app response'

    client.load('empty')

    hooked = _wait_cookie('worker_shutdown.*', processes)
    assert hooked, 'on_worker_shutdown called'
