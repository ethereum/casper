import rlp
from ethereum.utils import encode_hex


class InvalidCasperMessage(Exception):
    pass


class PrepareMessage(rlp.Serializable):

    fields = [
        ('hash', rlp.sedes.binary),
        ('view', rlp.sedes.big_endian_int),
        ('view_source', rlp.sedes.big_endian_int),
        ('signature', rlp.sedes.binary)
    ]

    def __init__(self, hash, view, view_source, signature=''):
        super(PrepareMessage, self).__init__(hash, view, view_source, signature)

    def validate(self):
        if not -1 <= self.view_source < self.view:
            raise InvalidCasperMessage('view_source not in range')

    @property
    def proposal(self):
        return "%d-%s" % (self.view, encode_hex(self.hash))

    def sign(self, privkey):
        self.signature = 'mock-sig'  # TODO: sign message


class CommitMessage(rlp.Serializable):

    fields = [
        ('hash', rlp.sedes.binary),
        ('view', rlp.sedes.big_endian_int),
        ('signature', rlp.sedes.binary)
    ]
