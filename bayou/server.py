import asyncio
import datetime
import logging
import os

from aiohttp import web

import simplejson


ENCODING = "UTF-8"


logger = logging.getLogger(__name__)


class Stream:
    def __init__(self, root):
        self.root = root
        self._file = None
        self._readers = []

    def __repr__(self):
        return "{0.__name__}({1.root!r})".format(type(self), self)

    def _notify(self, text, next_offset):
        futures = self._readers
        result = (text, next_offset)
        for future in futures:
            if future.done():
                continue
            future.set_result(result)
        futures.clear()

    @asyncio.coroutine
    def open(self, offset, loop=None):
        file = self._file
        if file is None:
            future = asyncio.Future(loop=loop)
            root = self.root
            if not os.path.exists(root):
                os.makedirs(root)
            file = open(os.path.join(root, "0.ldjson"), 'a+')
            future.set_result(file)
            self._file = future
        return file

    @asyncio.coroutine
    def append(self, data, loop=None):
        file = yield from self.open(None, loop=loop)
        file.seek(0, os.SEEK_END)
        obj = dict(
            data=data,
            offset=file.tell(),
            time="{}Z".format(datetime.datetime.utcnow().isoformat())
        )
        text = "{}\n".format(simplejson.dumps(obj, separators=(',', ':'), sort_keys=True))
        file.write(text)
        file.flush()
        self._notify(text, file.tell())
        return text

    @asyncio.coroutine
    def next_offset(self, since_offset, loop=None):
        if since_offset is None:
            return 0
        file = yield from self.open(since_offset, loop=loop)
        file.seek(since_offset)
        file.readline()
        return file.tell()

    @asyncio.coroutine
    def read(self, next_offset, loop=None):
        future = asyncio.Future(loop=loop)
        file = yield from self.open(next_offset, loop=loop)
        file.seek(next_offset)
        text = file.readline()
        if text:
            future.set_result((text, file.tell()))
        else:
            self._readers.append(future)
        return (yield from future)


class Handler:
    def __init__(self, root):
        self.root = root
        self._streams = {}

    def stream(self, name):
        cache = self._streams
        try:
            stream = cache[name]
        except KeyError:
            stream = Stream(os.path.join(self.root, name))
            cache[name] = stream
        return stream

    @asyncio.coroutine
    def append(self, request):
        loop = request.app.loop
        stream = self.stream(request.match_info['name'])
        try:
            data = yield from request.json(loader=simplejson.loads)
        except simplejson.JSONDecodeError:
            raise web.HTTPBadRequest
        text = yield from stream.append(data, loop=loop)
        return web.Response(
            body=text.encode(ENCODING),
            content_type="application/json; charset={}".format(ENCODING)
        )

    @asyncio.coroutine
    def read(self, request):
        loop = request.app.loop
        stream = self.stream(request.match_info['name'])

        response = web.StreamResponse()
        response.content_type = "application/ldjson; charset={}".format(ENCODING)
        response.start(request)

        try:
            since_offset = int(request.GET['since'])
        except KeyError:
            since_offset = None
        except ValueError:
            raise web.HTTPBadRequest

        next_offset = yield from stream.next_offset(since_offset, loop=loop)
        while True:
            text, next_offset = yield from stream.read(next_offset, loop=loop)
            response.write(text.encode(ENCODING))
            yield from response.drain()

        yield from response.write_eof()
        return response


@asyncio.coroutine
def start(root, address, port, loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()

    handler = Handler(root)
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/{name}', handler.read)
    app.router.add_route('POST', '/{name}', handler.append)

    server = yield from loop.create_server(app.make_handler(), address, port)
    return server
