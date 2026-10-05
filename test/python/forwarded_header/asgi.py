import json


async def application(scope, receive, send):
    metadata = json.dumps(
        {'client': scope['client'][0], 'scheme': scope['scheme']}
    ).encode()

    if scope['type'] == 'websocket':
        await receive()
        await send({'type': 'websocket.accept'})
        await send({'type': 'websocket.send', 'bytes': metadata})
        await send({'type': 'websocket.close'})
        return

    await send(
        {
            'type': 'http.response.start',
            'status': 200,
            'headers': [(b'content-length', str(len(metadata)).encode())],
        }
    )
    await send({'type': 'http.response.body', 'body': metadata})
