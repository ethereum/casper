

def test_rlp_decoding_is_pure(
        tester,
        purity_checker,
        vyper_rlp_decoder_address
        ):
    purity_return_val = purity_checker.functions.submit(vyper_rlp_decoder_address).call()
    assert purity_return_val == 1


def test_msg_hasher_is_pure(
        tester,
        purity_checker,
        msg_hasher_address,
        ):
    purity_return_val = purity_checker.functions.submit(msg_hasher_address).call()
    assert purity_return_val == 1


# sanity check on casper contract basic functionality
def test_init_first_epoch(tester, concise_casper, new_epoch, warm_up_period, epoch_length):
    block_number = tester.get_block_by_number('latest')['number']
    start_epoch = (block_number + warm_up_period) // epoch_length

    assert concise_casper.current_epoch() == start_epoch
    assert concise_casper.next_validator_index() == 1

    new_epoch()

    assert concise_casper.dynasty() == 0
    assert concise_casper.next_validator_index() == 1
    assert concise_casper.current_epoch() == start_epoch + 1
    assert concise_casper.total_slashed(concise_casper.current_epoch()) == 0
