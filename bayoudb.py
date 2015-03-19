#!/usr/bin/env python3.4

import asyncio
import datetime
import logging
import os

from aiohttp import web

import simplejson


ENCODING = "UTF-8"
ROOT = "/tmp/bayoudb"


logger = logging.getLogger(__name__)


class EventStream:
    _cache = {}

    def __init__(self, name):
        self.name = name
        self._file = None
        self._futures = []

    def __repr__(self):
        return "{0.__name__}({1.name!r})".format(type(self), self)

    @classmethod
    def cached(cls, name):
        cache = cls._cache
        try:
            instance = cache[name]
        except KeyError:
            instance = cls(name)
            cache[name] = instance
        return instance

    @property
    def path(self):
        return os.path.join(ROOT, self.name)

    def open(self):
        file = self._file
        if file is None:
            file = open(self.path, 'a+')
            self._file = file
        return file

    def _notify(self, text, offset):
        futures = self._futures
        result = (text, offset)
        for future in futures:
            if future.done():
                continue
            future.set_result(result)
        futures.clear()

    def append(self, data):
        file = self.open()
        file.seek(0, os.SEEK_END)
        obj = dict(
            data=data,
            offset=str(file.tell()),
            time="{}Z".format(datetime.datetime.utcnow().isoformat())
        )
        text = "{}\n".format(simplejson.dumps(obj, separators=(',', ':'), sort_keys=True))
        file.write(text)
        file.flush()
        self._notify(text, file.tell())
        return text

    def offset(self, since=None):
        if since is None:
            return 0
        file = self.open()
        file.seek(since)
        file.readline()
        return file.tell()

    @asyncio.coroutine
    def read(self, offset, loop=None):
        future = asyncio.Future(loop=loop)
        file = self.open()
        file.seek(offset)
        text = file.readline()
        if text:
            future.set_result((text, file.tell()))
        else:
            self._futures.append(future)
        return future


@asyncio.coroutine
def append_handler(request):
    event_stream = EventStream.cached(request.match_info['stream'])
    try:
        data = yield from request.json(loader=simplejson.loads)
    except simplejson.JSONDecodeError:
        raise web.HTTPBadRequest
    text = event_stream.append(data)
    return web.Response(
        body=text.encode(ENCODING),
        content_type="application/json; charset={}".format(ENCODING)
    )


@asyncio.coroutine
def read_handler(request):
    event_stream = EventStream.cached(request.match_info['stream'])

    response = web.StreamResponse()
    response.content_type = "application/ldjson; charset={}".format(ENCODING)
    response.start(request)

    loop = request.app.loop

    try:
        since = int(request.GET['since'])
    except KeyError:
        since = None
    except ValueError:
        raise web.HTTPBadRequest

    offset = event_stream.offset(since)
    while True:
        text, offset = yield from event_stream.read(offset, loop=loop)
        response.write(text.encode(ENCODING))
        yield from response.drain()

    yield from response.write_eof()
    return response


def main():
    logging.basicConfig(level=logging.DEBUG)

    if not os.path.exists(ROOT):
        os.makedirs(ROOT)

    loop = asyncio.get_event_loop()

    app = web.Application(loop=loop)
    app.router.add_route('GET', '/{stream}', read_handler)
    app.router.add_route('POST', '/{stream}', append_handler)

    loop.run_until_complete(loop.create_server(app.make_handler(), '127.0.0.1', 4430))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == '__main__':
    main()
