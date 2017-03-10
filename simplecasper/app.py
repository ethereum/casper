# -*- coding: utf8 -*-
import os
import signal
import sys
from logging import StreamHandler

import click
import gevent
from gevent.event import Event

import ethereum.slogging as slogging
from casper_service import CasperService
from chain_service import ChainService
from db_service import DBService
from devp2p.app import BaseApp
from devp2p.discovery import NodeDiscovery
from devp2p.peermanager import PeerManager
from devp2p.service import BaseService
from ethereum.utils import encode_hex, decode_hex, sha3, privtopub
from simplecasper import __version__

slogging.PRINT_FORMAT = '%(asctime)s %(name)s:%(levelname).1s\t%(message)s'
log = slogging.get_logger('app')

services = [NodeDiscovery, PeerManager, DBService, ChainService, CasperService]

privkeys = [encode_hex(sha3(i)) for i in range(100, 200)]
pubkeys = [encode_hex(privtopub(decode_hex(k))[1:]) for k in privkeys]


class SimpleCasper(BaseApp):
    client_name = 'simplecasper'
    client_version = '%s/%s/%s' % (__version__, sys.platform,
                                   'py%d.%d.%d' % sys.version_info[:3])
    client_version_string = '%s/v%s' % (client_name, client_version)
    start_console = False
    default_config = dict(BaseApp.default_config)
    default_config['client_version_string'] = client_version_string
    default_config['post_app_start_callback'] = None
    script_globals = {}


@click.group(help='Welcome to {} {}'.format(SimpleCasper.client_name, SimpleCasper.client_version))
@click.option('-l', '--log_config', multiple=False, type=str, default=":info",
              help='log_config string: e.g. ":info,eth:debug', show_default=True)
@click.option('--log-file', type=click.Path(dir_okay=False, writable=True, resolve_path=True),
              help="Log to file instead of stderr.")
@click.pass_context
def app(ctx, log_config, log_file):
    slogging.configure(log_config, log_file=log_file)
    ctx.obj = {
        'log_config': log_config,
        'log_file': log_file,
        'config': {
            'node': {
                'data_dir': 'data'
            },
            'casper': {
                'network_id': 0,
                'validator_id': 0,
                'privkey': ''
            },
            'discovery': {
                'listen_host': '0.0.0.0',
                'listen_port': 20170,
                'bootstrap_nodes': [
                    'enode://%s@127.0.0.1:20170' % pubkeys[0]
                ]
            },
            'p2p': {
                'listen_host': '0.0.0.0',
                'listen_port': 20170,
                'max_peers': 4,
                'min_peers': 4
            }
        }
    }


@app.command()
@click.argument('node_id', type=click.IntRange(0,100))
@click.option('--console',  is_flag=True, help='Immediately drop into interactive console.')
@click.pass_context
def run(ctx, node_id, console):
    """Start the daemon"""
    config = ctx.obj['config']
    config['node']['privkey_hex'] = privkeys[node_id]
    config['node']['data_dir'] += str(node_id)
    config['discovery']['listen_port'] += node_id
    config['p2p']['listen_port'] += node_id
    config['casper']['privkey'] = decode_hex(config['node']['privkey_hex'])
    log.info("starting", config=config)

    if config['node']['data_dir'] and not os.path.exists(config['node']['data_dir']):
        os.makedirs(config['node']['data_dir'])

    app = SimpleCasper(config)
    app.start_console = console

    for service in services:
        assert issubclass(service, BaseService)
        assert service.name not in app.services
        service.register_with_app(app)
        assert hasattr(app.services, service.name)

    # start app
    log.info('starting')
    app.start()

    if ctx.obj['log_file']:
        log.info("Logging to file %s", ctx.obj['log_file'])
        # User requested file logging - remove stderr handler
        root_logger = slogging.getLogger()
        for hdl in root_logger.handlers:
            if isinstance(hdl, StreamHandler) and hdl.stream == sys.stderr:
                root_logger.removeHandler(hdl)
                break

    # wait for interrupt
    evt = Event()
    gevent.signal(signal.SIGQUIT, evt.set)
    gevent.signal(signal.SIGTERM, evt.set)
    evt.wait()

    # finally stop
    app.stop()


if __name__ == '__main__':
    app()
