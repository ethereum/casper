import rlp
from casper_messages import PrepareMessage, CommitMessage
from devp2p.protocol import BaseProtocol, SubProtocolError
from ethereum import slogging

log = slogging.get_logger('protocol.csp')


class CasperProtocolError(SubProtocolError):
    pass


class CasperProtocol(BaseProtocol):

    """
    Simple Casper Wire Protocol
    https://docs.google.com/document/d/1ecFPYhe7YsKNQUAx48S8hoyK9Y4Rbe9be_lCe_vj2ek/edit
    """
    protocol_id = 200
    network_id = 0
    max_cmd_id = 15
    name = 'csp'
    version = 1

    def __init__(self, peer, service):
        # required by P2PProtocol
        self.config = peer.config
        BaseProtocol.__init__(self, peer, service)

    class status(BaseProtocol.command):
        cmd_id = 0
        sent = False

        structure = [
            ('csp_version', rlp.sedes.big_endian_int),
            ('network_id', rlp.sedes.big_endian_int),
            ('chain_difficulty', rlp.sedes.big_endian_int),
            ('chain_head_hash', rlp.sedes.binary),
            ('genesis_hash', rlp.sedes.binary)]

        def create(self, proto, chain_difficulty, chain_head_hash, genesis_hash):
            self.sent = True
            network_id = proto.service.app.config['casper'].get('network_id', proto.network_id)
            return [proto.version, network_id, chain_difficulty, chain_head_hash, genesis_hash]

    class prepare(BaseProtocol.command):
        """
        prepare(HASH, view, view_source), -1 <= view_source < view
        """
        cmd_id = 1
        structure = [('prepare', PrepareMessage)]

    class commit(BaseProtocol.command):
        """
        commit(HASH, view), 0 <= view
        """
        cmd_id = 2
        structure = [('commit', CommitMessage)]
