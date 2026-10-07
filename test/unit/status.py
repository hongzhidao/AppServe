from unit.control import Control


class Status:
    _status = None
    control = Control()

    def _check_zeros():
        assert Status.control.conf_get('/status') == {
            'requests': {'total': 0, 'active': 0, 'completed': 0, 'failed': 0},
            'applications': {},
            'processes': {
                'busy': 0,
                'idle': 0,
            },
            'responses': {'1xx': 0, '2xx': 0, '3xx': 0, '4xx': 0, '5xx': 0},
            'latency': {'sum': 0, 'avg': 0, 'max': 0},
        }

    def init(status=None):
        Status._status = (
            status if status is not None else Status.control.conf_get('/status')
        )

    def diff():
        def find_diffs(d1, d2):
            if isinstance(d1, dict) and isinstance(d2, dict):
                return {
                    k: find_diffs(d1.get(k, 0), d2.get(k, 0))
                    for k in d1
                    if k in d2
                }
            else:
                return d1 - d2

        return find_diffs(Status.control.conf_get('/status'), Status._status)

    def get(path='/'):
        path = path.split('/')[1:]
        diff = Status.diff()

        for p in path:
            diff = diff[p]

        return diff
