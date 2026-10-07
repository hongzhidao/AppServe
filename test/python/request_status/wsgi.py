import time


def application(environ, start_response):
    if environ.get('HTTP_X_DELAY'):
        start_response('200', [])

        def body():
            yield b'ready'
            time.sleep(float(environ['HTTP_X_DELAY']))
            yield b'x' * 65536
            time.sleep(0.1)
            yield b'done'

        return body()

    headers = [('Content-Length', '0')]
    if environ.get('HTTP_X_INVALID_STATUS'):
        headers.append(('Status', 'invalid'))
    start_response(environ.get('HTTP_X_STATUS', '200'), headers)
    return []
