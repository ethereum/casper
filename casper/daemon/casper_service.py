import traceback
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
            privkey='\x00'*32,
            epoch_length=5,
            genesis_hash=''  # genesis of Casper, not block#0, must be on epoch boundary
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
            if db_network_id != str(cfg['network_id']).encode():
                raise RuntimeError(
                    "The database in '{}' was initialized with network id {} and can not be used "
                    "when connecting to network id {}. Please choose a different data directory.".format(
                        app.config['db']['data_dir'], db_network_id, cfg['network_id']
                    )
                )
        else:
            self.db.put('network_id', str(cfg['network_id']))
            self.db.commit()

        self.epoch_length = cfg['epoch_length']
        self.epoch_source = -1
        self.epoch = 0
        self.ancestry_hash = sha3('')
        self.source_ancestry_hash = sha3('')

        self.chain = app.services.chain
        self.genesis = self.chain.block(cfg['genesis_hash'])
        assert self.genesis
        assert self.genesis['number'] % self.epoch_length == 0

        self.store = LevelDBStore(self.db, self.epoch_length, self.genesis)
        self.validator = self.store.validator(cfg['validator_id'])
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
            try:
                # TODO: what if we received a blk on a new fork?
                self.store.save_block(blk)
            except KeyError:
                self.sync_epoch(blk)
            self.check_checkpoint(self.checkpoint_for(blk))
            self.try_prepare()
        except KeyError:
            log.debug(traceback.format_exc())
            log.error('failed to save block', hash=blk['hash'])

    def sync_epoch(self, blk):
        epoch_blocks = [blk]
        while blk['number'] % self.epoch_length != 0:
            blk = self.chain.block(blk['parentHash'])
            epoch_blocks.insert(0, blk)
        for b in epoch_blocks:
            self.store.save_block(b)
            log.info("syncing epoch", number=b['number'], hash=b['hash'])
        log.info("epoch %d synced" % (blk['number'] // self.epoch_length))

    def check_checkpoint(self, block):
        '''
        Check if candidate committed, if so persist to db.
        '''
        if not self.store.checkpoint(block['hash']):
            # TODO: check quorum and persist
            self.store.add_checkpoint(block['hash'])

    def checkpoint_for(self, blk):
        hash = self.store.tail_membership(blk['hash'])
        return self.store.block(hash)

    def get_last_committed_checkpoint(self):
        z = self.store.checkpoint_count() - 1
        while True:
            hash = self.store.checkpoint_at(z)
            if self.is_committed(hash):
                return self.store.block(hash)
            else:
                z -= 1

    def is_committed(self, hash):
        if hash == self.genesis['hash']:
            return True
        # TODO: better committed check
        return len(self.store.commits_for(hash)) > 0

    def is_ancestor(self, blk1, blk2):
        '''
        Return true if blk2 is blk1's ancestor.
        '''
        # TODO: implement
        return True

    def try_prepare(self):
        target_block = self.store.block(self.store.last_checkpoint())
        target_epoch = target_block['number'] // self.epoch_length
        last_committed_checkpoint = self.get_last_committed_checkpoint()
        if target_epoch > self.epoch:
            # TODO: self.epoch need to be persist to prevent double prepare?
            self.epoch = target_epoch
            if self.is_ancestor(target_block, last_committed_checkpoint):
                self.broadcast_prepare(target_block, last_committed_checkpoint)

    def broadcast_prepare(self, checkpoint, last_committed_checkpoint, origin=None):
        log.debug('broadcast prepare message',
                  number=checkpoint['number'],
                  hash=checkpoint['hash'])

        epoch = checkpoint['number'] // self.epoch_length
        epoch_source = last_committed_checkpoint['number'] // self.epoch_length
        prepare = PrepareMessage(
            validator_id=self.validator.id,
            epoch=epoch,
            hash=checkpoint['hash'],
            epoch_source=epoch_source
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
