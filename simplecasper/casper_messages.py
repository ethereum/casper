import rlp
from ethereum.utils import encode_hex


class InvalidCasperMessage(Exception):
    pass


class PrepareMessage(rlp.Serializable):

    fields = [
        ('validator_id', rlp.sedes.big_endian_int),
        ('epoch', rlp.sedes.big_endian_int),
        ('hash', rlp.sedes.binary),
        ('ancestry_hash', rlp.sedes.binary),
        ('epoch_source', rlp.sedes.big_endian_int),
        ('source_ancestry_hash', rlp.sedes.binary),
        ('signature', rlp.sedes.binary)
    ]

    def __init__(self, validator_id, epoch, hash, ancestry_hash, epoch_source, source_ancestry_hash, signature=''):
        super(PrepareMessage, self).__init__(
            validator_id,epoch, hash, ancestry_hash, epoch_source, source_ancestry_hash, signature
        )

    def validate(self):
        if not -1 <= self.epoch_source < self.epoch:
            raise InvalidCasperMessage('view_source not in range')

    @property
    def proposal(self):
        return "%d-%s" % (self.epoch, encode_hex(self.hash))

    def sign(self, privkey):
        self.signature = 'mock-sig'  # TODO: sign message


class CommitMessage(rlp.Serializable):

    fields = [
        ('validator_id', rlp.sedes.big_endian_int),
        ('epoch', rlp.sedes.big_endian_int),
        ('hash', rlp.sedes.binary),
        ('signature', rlp.sedes.binary)
    ]
