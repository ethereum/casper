from ethereum import utils


def test_rlp_decoding_is_pure(
        casper_chain,
        base_sender_privkey,
        viper_rlp_decoder_address,
        purity_checker_address,
        purity_checker_ct
        ):
    purity_return_val = casper_chain.tx(
        base_sender_privkey,
        purity_checker_address,
        0,
        purity_checker_ct.encode('submit', [viper_rlp_decoder_address])
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


def test_contract_deployed(casper):
    assert casper.nextValidatorIndex() == 1
    assert casper.current_epoch() == 0
