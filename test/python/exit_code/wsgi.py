import os


def application(environ, start_response):
    if 'HTTP_X_EXIT_CODE' in environ:
        os._exit(int(environ['HTTP_X_EXIT_CODE']))

    start_response('200 OK', [
        ('Content-Length', '0'),
        ('X-Pid', str(os.getpid())),
    ])
    return []
