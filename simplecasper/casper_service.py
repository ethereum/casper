from casper_messages import InvalidCasperMessage, PrepareMessage
from casper_protocol import CasperProtocol
from devp2p.service import WiredService
from ethereum import slogging
from ethereum.utils import encode_hex, sha3
from leveldb_store import LevelDBStore

log = slogging.get_logger('casper.service')


class CasperService(WiredService):

    name = 'casper'
    default_config = dict(
        casper=dict(
            network_id=0,
            validator_id=0,
            privkey='\x00'*32
        )
    )

    # required by WiredService
    wire_protocol = CasperProtocol  # create for each peer

    def __init__(self, app):
        log.info("Casper service init")
        self.db = app.services.db
        self.bcast = app.services.peermanager.broadcast

        cfg = app.config['casper']
        self.account = app.services.accounts.get_by_address(app.services.accounts.coinbase)
        self.privkey = self.account.privkey
        if 'network_id' in self.db:
            db_network_id = self.db.get('network_id')
            if db_network_id != str(cfg['network_id']):
                raise RuntimeError(
                    "The database in '{}' was initialized with network id {} and can not be used "
                    "when connecting to network id {}. Please choose a different data directory.".format(
                        app.config['db']['data_dir'], db_network_id, cfg['network_id']
                    )
                )
        else:
            self.db.put('network_id', str(cfg['network_id']))
            self.db.commit()

        self.store = LevelDBStore(self.db)
        self.validator = self.store.load_validator(cfg['validator_id'])
        self.block = None
        self.epoch_block = None
        self.epoch_length = 5
        self.epoch_source = -1
        self.epoch = 0
        self.ancestry_hash = sha3('')
        self.source_ancestry_hash = sha3('')

        super(CasperService, self).__init__(app)

    def on_wire_protocol_start(self, proto):
        log.debug('----------------------------------')
        log.debug('on_wire_protocol_start', proto=proto)
        assert isinstance(proto, self.wire_protocol)
        # register callbacks
        proto.receive_status_callbacks.append(self.on_receive_status)
        proto.receive_prepare_callbacks.append(self.on_receive_prepare)
        proto.receive_commit_callbacks.append(self.on_receive_commit)

        # TODO: send status
        status_mock = (0, '', '')
        proto.send_status(chain_difficulty=status_mock[0],
                          chain_head_hash=status_mock[1],
                          genesis_hash=status_mock[2])

    def on_wire_protocol_stop(self, proto):
        assert isinstance(proto, self.wire_protocol)
        log.debug('----------------------------------')
        log.debug('on_wire_protocol_stop', proto=proto)

    def on_receive_status(self, proto, csp_version, network_id, chain_difficulty, chain_head_hash, genesis_hash):
        pass

    def on_receive_prepare(self, proto, prepare):
        log.debug('on receive prepare',
                  hash=encode_hex(prepare.hash),
                  epoch=prepare.epoch,
                  epoch_source=prepare.epoch_source,
                  peer=proto.peer)
        try:
            prepare.validate()
            self.store.save_prepare(prepare)
            self.store.commit()
        except InvalidCasperMessage as e:
            log.error('invalid casper message received',
                      reason=e,
                      peer=proto.peer)

    def on_receive_commit(self, proto, commit):
        pass

    def on_new_block(self, blk):
        log.info('on new block', block=blk)

        try:
            self.store.save_block(blk)
            self.block = blk
            # the blk comes from geth/parity, we just assume it's valid and skip PoW check

            new_epoch = blk['number'] // self.epoch_length
            if new_epoch != self.epoch:
                self.epoch_source = self.epoch
                self.epoch_block = blk
                self.epoch = new_epoch

            self.move()
        except KeyError:
            log.error('failed to save block', hash=blk['hash'])

    def move(self):
        if self.is_commitable():
            self.broadcast_commit()
        if self.is_preparable():
            self.broadcast_prepare()

    def is_commitable(self):
        return False

    def is_preparable(self):
        if self.epoch_source != -1:
            pass  # TODO: check epoch_source/ancestor_hash quorum
        if self.store.load_my_prepare(self.epoch):
            return False
        if not self.epoch_block:
            number = self.epoch * self.epoch_length
            candidates = self.store.load_blocks_by_number(number)
            if len(candidates) > 0:
                self.epoch_block = candidates[0]  # TODO: better candidate selection strategy
            else:
                log.warn("missing epoch block, cannot prepare",
                         epoch=self.epoch,
                         number=number)
                return False
        return True

    def broadcast_prepare(self, origin=None):
        log.debug('broadcast prepare message',
                  number=self.block['number'],
                  hash=self.block['hash'])

        prepare = PrepareMessage(
            validator_id=self.validator.id,
            epoch=self.epoch,
            hash=self.block['hash'],
            ancestry_hash=self.ancestry_hash,
            epoch_source=self.epoch_source,
            source_ancestry_hash=self.source_ancestry_hash
        )
        prepare.sign(self.privkey)
        self.store.save_prepare(prepare, my=True)
        self.store.commit()

        self.bcast(CasperProtocol,
                   'prepare',
                   args=(prepare,),
                   exclude_peers=[origin.peer] if origin else [])

    def broadcast_commit(self):
        pass
