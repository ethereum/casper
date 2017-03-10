import json

import rlp
from casper_messages import PrepareMessage
from validators import Validator
from ethereum.utils import encode_hex

validators = [
    Validator(
        id=0,
        deposit=100000000000000000000,
        dynasty_start=0,
        dynasty_end=100000000000000000,
        withdrawal_time=100000000000000000000,
        withdrawal_addr='',
        addr='',
        max_prepared=0,
        max_committed=0
    )
]


class LevelDBStore(object):

    def __init__(self, db):
        self.db = db

        try:
            self.db.get('HEAD')
        except KeyError:
            self.init_db()

    def init_db(self):
        self.db.put('HEAD', rlp.encode(0, sedes=rlp.sedes.big_endian_int))

    def load_validator(self, id):
        # TODO: load from db
        # return rlp.decode(self.db.get('validator_%d' % id), sedes=Validator)
        return validators[id]

    def load_blocks_by_number(self, number):
        key = "block_by_number_%d" % number
        try:
            hashes = self.db.get(key)
            return [self.load_block(h) for h in hashes]
        except KeyError:
            return []

    def load_block(self, hash):
        try:
            if len(hash) == 32:
                hash = '0x' + encode_hex(hash)
            return json.loads(self.db.get(hash))
        except KeyError:
            return None

    def save_block(self, block):
        self._save_block(block)
        self._update_block_index(block)
        self._update_head(block)

    def _save_block(self, block):
        try:
            self.db.get(block['hash'])
            raise KeyError("block already in db")
        except KeyError:
            self.db.put(block['hash'], json.dumps(block))

    def _update_block_index(self, block):
        key = "block_by_number_%d" % block['number']
        try:
            hashes = rlp.decode(self.db.get(key))
        except KeyError:
            hashes = []
        hashes.append(block['hash'])
        self.db.put(key, rlp.encode(hashes))

    def _update_head(self, block):
        head = rlp.decode(self.db.get('HEAD'), sedes=rlp.sedes.big_endian_int)
        if block['number'] > head:
            self.db.put('HEAD', rlp.encode(block['number'], sedes=rlp.sedes.big_endian_int))

    def load_my_prepare(self, epoch):
        try:
            return rlp.decode(self.db.get('epoch_%d_prepare' % epoch), sedes=PrepareMessage)
        except KeyError:
            return None

    def save_prepare(self, prepare, my=False):
        if my:
            self.db.put('epoch_%d_prepare' % prepare.epoch, rlp.encode(prepare))

        # save prepares for certain proposal
        count_key = 'prepare_count_%s' % prepare.proposal
        try:
            count = rlp.decode(self.db.get(count_key), sedes=rlp.sedes.big_endian_int)
        except KeyError:
            count = 0
        self.db.put('prepare_%s_%d' % (prepare.proposal, count), rlp.encode(prepare))
        self.db.put(count_key, rlp.encode(count+1, sedes=rlp.sedes.big_endian_int))

    def save_commit(self):
        pass

    def commit(self):
        self.db.commit()
