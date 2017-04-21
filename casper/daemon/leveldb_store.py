import json

import rlp
from casper_messages import PrepareMessage
from validators import Validator
from ethereum.utils import encode_hex
from ethereum import slogging


log = slogging.get_logger('leveldb.store')


validators = [
    Validator(
        id=0,
        deposit=100000000000000000000,
        dynasty_start=0,
        original_dynasty_start=0,
        dynasty_end=100000000000000000,
        withdrawal_epoch=100000000000000000000,
        addr='',
        withdrawal_addr='',
        prev_commit_epoch=0,
        max_prepared=0,
        max_committed=0
    )
]


class LevelDBStore(object):

    epoch_length_key = 'epoch_length'
    genesis_key = 'genesis'
    current_epoch_key = 'cur'
    checkpoint_count_key = 'cpcount'
    checkpoint_key_ = 'cp_%d'
    tail_key_ = 'tail_%s'
    tail_membership_key_ = 'tail_mbs_%s'
    number_blockhashes_key_ = 'index_num_bhs_%d'
    my_prepare_key_ = 'my_epoch_%d_pp'
    prepare_count_key_ = 'ppcount_for_%s'
    prepare_key_ = 'pp_for_%s_%d'

    def __init__(self, db, epoch_length, genesis):
        self.db = db
        try:
            assert genesis['hash'] == self.genesis()['hash']
            assert epoch_length == self.epoch_length()
        except KeyError:
            self.init_db(epoch_length, genesis)

    def init_db(self, epoch_length, genesis):
        self.put_json(self.genesis_key, genesis)
        self.put_int(self.epoch_length_key, epoch_length)
        self.put_int(self.current_epoch_key, 0)
        self.put_int(self.checkpoint_count_key, 0)
        self.save_block(genesis, True)
        log.info("db initialized")

    def epoch_length(self):
        return self.get_int(self.epoch_length_key)

    def genesis(self):
        return self.get_json(self.genesis_key)

    def current_epoch(self):
        return self.get_int(self.current_epoch_key)

    def checkpoint_count(self):
        return self.get_int(self.checkpoint_count_key)

    def last_checkpoint(self):
        return self.checkpoint(self.checkpoint_count()-1)

    def checkpoint(self, index):
        if index < 0 or index >= self.checkpoint_count():
            return None
        return self.get_bin(self.checkpoint_key_ % index)

    def add_checkpoint(self, hash):
        index = self.checkpoint_count()
        self.put_bin(self.checkpoint_key_ % index, hash)
        self.put_int(self.checkpoint_count_key, index+1)
        return index+1

    def tail(self, hash):
        return self.get_json(self.tail_key_ % hash)

    def save_tail(self, cp_hash, blk):
        self.put_json(self.tail_key_ % cp_hash, blk)

    def tail_membership(self, hash):
        return self.get_bin(self.tail_membership_key_ % hash)

    def save_tail_membership(self, hash, cp_hash):
        self.put_bin(self.tail_membership_key_ % hash, cp_hash)

    def blockhashes(self, number):
        try:
            return self.get_list(self.number_blockhashes_key_ % number)
        except KeyError:
            return []

    def _update_number_blockhashes_index(self, number, hash):
        k = self.number_blockhashes_key_ % number
        try:
            hashes =  self.get_list(k)
        except KeyError:
            hashes = []
        hashes.append(hash)
        self.put_list(k, hashes)

    def validator(self, id):
        # TODO: load from db
        # return rlp.decode(self.db.get('validator_%d' % id), sedes=Validator)
        return validators[id]

    def blocks_by_number(self, number):
        try:
            return [self.block(h) for h in self.blockhashes(number)]
        except KeyError:
            return []

    def block(self, hash):
        try:
            if len(hash) == 32:
                hash = '0x' + encode_hex(hash)
            return self.get_json(hash)
        except KeyError:
            return None

    def save_block(self, block, epoch_start):
        self._update_block_index(block, epoch_start)
        self._save_block(block)
        log.debug("block saved", hash=block['hash'])

    def _save_block(self, block):
        assert not self.block(block['hash'])
        self.put_json(block['hash'], block)

    def _update_block_index(self, block, epoch_start):
        self._update_number_blockhashes_index(block['number'], block['hash'])
        if epoch_start:
            self.save_tail_membership(block['hash'], block['hash'])
            self.save_tail(block['hash'], block)
        else:
            parent_cp_hash = self.tail_membership(block['parentHash'])
            self.save_tail_membership(block['hash'], parent_cp_hash)
            parent_tail = self.tail(parent_cp_hash)
            if block['number'] > parent_tail['number']:
                self.save_tail(parent_cp_hash, block)

    def my_prepare(self, epoch):
        try:
            return rlp.decode(self.db.get(self.my_prepare_key_ % epoch), sedes=PrepareMessage)
        except KeyError:
            return None

    def save_prepare(self, prepare, my=False):
        if my:
            self.db.put(self.my_prepare_key_ % prepare.epoch, rlp.encode(prepare))

        # save prepares for certain proposal
        count_key = self.prepare_count_key_ % prepare.proposal
        try:
            count = self.get_int(count_key)
        except KeyError:
            count = 0
        self.db.put(self.prepare_key_ % (prepare.proposal, count), rlp.encode(prepare))
        self.put_int(count_key, count+1)

    def save_commit(self):
        pass

    def commit(self):
        self.db.commit()

    def put_json(self, k, v):
        self.db.put(k, json.dumps(v))

    def get_json(self, k):
        return json.loads(self.db.get(k))

    def put_list(self, k, v, element_sedes=rlp.sedes.binary):
        sedes = rlp.sedes.CountableList(element_sedes)
        self.db.put(k, rlp.encode(v, sedes=sedes))

    def get_list(self, k, element_sedes=rlp.sedes.binary):
        sedes = rlp.sedes.CountableList(element_sedes)
        return list(rlp.decode(self.db.get(k), sedes=sedes))

    def put_bin(self, k, v):
        self.db.put(k, v)

    def get_bin(self, k):
        return self.db.get(k)

    def put_int(self, k, i):
        self.db.put(k, rlp.encode(i, sedes=rlp.sedes.big_endian_int))

    def get_int(self, k):
        return rlp.decode(self.db.get(k), sedes=rlp.sedes.big_endian_int)

