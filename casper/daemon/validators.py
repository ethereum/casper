import rlp


class Validator(rlp.Serializable):

    fields = [
        ('id', rlp.sedes.big_endian_int),
        ('deposit', rlp.sedes.big_endian_int),
        ('dynasty_start', rlp.sedes.big_endian_int),
        ('original_dynasty_start', rlp.sedes.big_endian_int),
        ('dynasty_end', rlp.sedes.big_endian_int),
        ('withdrawal_epoch', rlp.sedes.big_endian_int),
        ('addr', rlp.sedes.binary),
        ('withdrawal_addr', rlp.sedes.binary),
        ('prev_commit_epoch', rlp.sedes.big_endian_int),
        ('max_prepared', rlp.sedes.big_endian_int),
        ('max_committed', rlp.sedes.big_endian_int)
    ]


class Dynasty(rlp.Serializable):

    fields = [
        ('id', rlp.sedes.big_endian_int),
        ('validator_ids', rlp.sedes.CountableList(rlp.sedes.big_endian_int))
    ]
