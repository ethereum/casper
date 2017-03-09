import rlp
from validators import Validator


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

    def load_validator(self, id):
        # TODO: load from db
        # return rlp.decode(self.db.get('validator_%d' % id), sedes=Validator)
        return validators[id]

    def save_prepare(self, prepare):
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
