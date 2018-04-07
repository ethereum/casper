from ethereum import utils


def test_rlp_decoding_is_pure(
        casper_chain,
        base_sender_privkey,
        vyper_rlp_decoder_address,
        purity_checker_address,
        purity_checker_ct
        ):
    purity_return_val = casper_chain.tx(
        base_sender_privkey,
        purity_checker_address,
        0,
        purity_checker_ct.encode('submit', [vyper_rlp_decoder_address])
    )
    assert utils.big_endian_to_int(purity_return_val) == 1


def test_sig_hasher_is_pure(
        casper_chain,
        base_sender_privkey,
        sig_hasher_address,
        purity_checker_address,
        purity_checker_ct
        ):
    purity_return_val = casper_chain.tx(
        base_sender_privkey,
        purity_checker_address,
        0,
        purity_checker_ct.encode('submit', [sig_hasher_address])
    )
    assert utils.big_endian_to_int(purity_return_val) == 1


# sanity check on casper contract basic functionality
def test_init_first_epoch(casper, new_epoch):
    assert casper.current_epoch() == 0
    assert casper.next_validator_index() == 1

    new_epoch()

    assert casper.dynasty() == 0
    assert casper.next_validator_index() == 1
    assert casper.current_epoch() == 1
