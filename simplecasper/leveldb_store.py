import rlp


class LevelDBStore(object):

    def __init__(self, db):
        self.db = db

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
