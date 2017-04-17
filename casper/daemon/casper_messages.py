import rlp
from ethereum.utils import encode_hex, sha3, encode_int32, ecsign, parse_as_bin
from ethereum import slogging

log = slogging.get_logger('casper.message')


def sign(hash, privkey):
    assert len(privkey) == 32
    v, r, s = ecsign(hash, privkey)
    return encode_int32(v) + encode_int32(r) + encode_int32(s)


def normalize_hash(hash):
    if len(hash) != 32:
        hash = parse_as_bin(hash)
    assert len(hash) == 32
    return hash


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
        hash = normalize_hash(hash)
        ancestry_hash = normalize_hash(ancestry_hash)
        source_ancestry_hash = normalize_hash(source_ancestry_hash)

        super(PrepareMessage, self).__init__(
            validator_id, epoch, hash, ancestry_hash, epoch_source, source_ancestry_hash, signature
        )

    def validate(self):
        if not -1 <= self.epoch_source < self.epoch:
            raise InvalidCasperMessage('epoch_source not in range')

    @property
    def proposal(self):
        return "%d-%s" % (self.epoch, encode_hex(self.hash))

    @property
    def signing_hash(self):
        return sha3(
            'prepare%s%s%s%s%s' % (
                encode_int32(self.epoch),
                self.hash,
                self.ancestry_hash,
                encode_int32(self.epoch_source),
                self.source_ancestry_hash
            )
        )

    def sign(self, privkey):
        sign(self.signing_hash, privkey)


class CommitMessage(rlp.Serializable):

    fields = [
        ('validator_id', rlp.sedes.big_endian_int),
        ('epoch', rlp.sedes.big_endian_int),
        ('hash', rlp.sedes.binary),
        ('signature', rlp.sedes.binary)
    ]

    @property
    def signing_hash(self):
        return sha3(
            'commit%s%s' % (
                encode_int32(self.epoch),
                self.hash
            )
        )

    def sign(self, privkey):
        sign(self.signing_hash, privkey)
