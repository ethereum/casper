from gevent.event import Event
from web3 import Web3, KeepAliveRPCProvider
from ethereum import slogging

from devp2p.service import BaseService

log = slogging.get_logger('chain')


class ChainService(BaseService):

    name = 'chain'
    default_config = dict(
        chain=dict(
            provider='jsonrpc',
            jsonrpc=dict(
                host='127.0.0.1',
                port=8545
            )
        )
    )

    def __init__(self, app):
        log.info("Chain service init")
        super(ChainService, self).__init__(app)

        if self.app.config['chain']['provider'] == 'jsonrpc':
            self.web3 = Web3(KeepAliveRPCProvider(
                host=self.app.config['chain']['jsonrpc']['host'],
                port=self.app.config['chain']['jsonrpc']['port']
            ))
        else:
            raise ValueError("unsupported chain provider %s" %
                             self.app.config['chain']['provider'])

    def _run(self):
        self.start_filters()

        evt = Event()
        evt.wait()

    def stop(self):
        super(ChainService, self).stop()

    def start_filters(self):
        blk_filter = self.web3.eth.filter('latest')
        blk_filter.watch(self.on_new_block)

    def on_new_block(self, hash):
        log.info("new block", blockhash=hash)

        blk = self.web3.eth.getBlock(block_identifier=hash)
        self.app.services.casper.on_new_block(blk)

    def block(self, hash):
        return self.web3.eth.getBlock(block_identifier=hash)

