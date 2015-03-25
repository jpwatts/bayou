#!/usr/bin/env python

import asyncio
import logging

import click

from . import server


logger = logging.getLogger(__name__)


@click.command()
@click.option('--logging', '-l', default="WARNING", help="Log level", show_default=True)
@click.option('--address', '-a', default="127.0.0.1", help="Server address", show_default=True)
@click.option('--port', '-p', default=8000, help="Server port", show_default=True)
@click.option('--data', '-d', default=".", help="Data directory", show_default=True)
def main(**options):
    logging.basicConfig(level=getattr(logging, options['logging'].upper()))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        server.start(
            options['data'],
            options['address'],
            options['port'],
            loop=loop
        )
    )

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == '__main__':
    main()
