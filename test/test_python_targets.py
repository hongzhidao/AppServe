from unit.applications.lang.python import ApplicationPython
from unit.option import option

prerequisites = {'modules': {'python': 'all'}}


client = ApplicationPython()


def test_python_targets():
    assert 'success' in client.conf(
        {
            "listeners": {"*:8080": {"pass": "applications/targets$uri"}},
            "applications": {
                "targets": {
                    "type": "python",
                    "working_directory": option.test_dir
                    + "/python/targets/",
                    "path": option.test_dir + '/python/targets/',
                    "targets": {
                        "1": {
                            "module": "wsgi",
                            "callable": "wsgi_target_a",
                        },
                        "2": {
                            "module": "wsgi",
                            "callable": "wsgi_target_b",
                        },
                    },
                }
            },
        }
    )

    resp = client.get(url='/1')
    assert resp['status'] == 200
    assert resp['body'] == '1'

    resp = client.get(url='/2')
    assert resp['status'] == 200
    assert resp['body'] == '2'
