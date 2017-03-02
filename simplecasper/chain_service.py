from devp2p.service import BaseService


class ChainService(BaseService):

    name = 'chain'
    default_config = dict(
        chain=dict(
            jsonrpc_ip='0.0.0.0',
            jsonrpc_port=8545
        )
    )

    def __init__(self, app):
        super(ChainService, self).__init__(app)
        self.ip = self.app.config['chain']['jsonrpc_ip']
        self.port = self.app.config['chain']['jsonrpc_port']

    def _run(self):
        pass

    def stop(self):
        super(ChainService, self).stop()