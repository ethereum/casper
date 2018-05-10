# ensure that our fixture 'new_epoch' functions properly
def test_new_epoch_fixture(casper_chain, casper, new_epoch):
    epoch_length = casper.EPOCH_LENGTH()
    for _ in range(4):
        prev_epoch = casper.current_epoch()
        prev_block_number = casper_chain.head_state.block_number
        expected_jump = epoch_length - (prev_block_number % epoch_length)

        new_epoch()

        block_number = casper_chain.head_state.block_number
        assert casper.current_epoch() == prev_epoch + 1
        assert block_number == prev_block_number + expected_jump
        assert (block_number % epoch_length) == 0


def test_early_epoch_initialization(casper_chain, casper, new_epoch, assert_tx_failed):
    epoch_length = casper.EPOCH_LENGTH()

    new_epoch()

    for _ in range(0, epoch_length):
        casper_chain.mine(1)
        block_number = casper_chain.head_state.block_number
        is_epoch_block = (block_number % epoch_length) == 0
        next_epoch = casper.current_epoch() + 1
        if is_epoch_block:
            casper.initialize_epoch(next_epoch)
            assert casper.current_epoch() == next_epoch
        else:
            assert_tx_failed(
                lambda: casper.initialize_epoch(next_epoch)
            )


def test_double_epoch_initialization(casper_chain, casper, new_epoch, assert_tx_failed):
    new_epoch()
    initial_epoch = casper.current_epoch()

    casper_chain.mine(casper.EPOCH_LENGTH())

    next_epoch = initial_epoch + 1
    casper.initialize_epoch(next_epoch)
    assert casper.current_epoch() == next_epoch
    assert_tx_failed(
        lambda: casper.initialize_epoch(next_epoch)
    )


def test_epoch_initialization_one_block_late(casper_chain, casper, new_epoch):
    epoch_length = casper.EPOCH_LENGTH()

    new_epoch()
    initial_epoch = casper.current_epoch()

    casper_chain.mine(epoch_length + 1)
    assert (casper_chain.head_state.block_number % epoch_length) == 1

    expected_epoch = initial_epoch + 1
    casper.initialize_epoch(expected_epoch)

    assert casper.current_epoch() == expected_epoch


def test_epoch_initialize_one_epoch_late(casper_chain, casper, new_epoch, assert_tx_failed):
    new_epoch()
    initial_epoch = casper.current_epoch()

    casper_chain.mine(casper.EPOCH_LENGTH() * 2)
    assert_tx_failed(
        lambda: casper.initialize_epoch(initial_epoch + 2)
    )
    assert casper.current_epoch() == initial_epoch
    casper.initialize_epoch(initial_epoch + 1)
    assert casper.current_epoch() == initial_epoch + 1
    casper.initialize_epoch(initial_epoch + 2)
    assert casper.current_epoch() == initial_epoch + 2


def test_checkpoint_hashes(casper_chain, casper, new_epoch):
    for _ in range(4):
        next_epoch = casper.current_epoch() + 1
        epoch_length = casper.EPOCH_LENGTH()

        casper_chain.mine(epoch_length * next_epoch - casper_chain.head_state.block_number)

        casper.initialize_epoch(next_epoch)
        current_epoch = casper.current_epoch()
        # This looks incorrect but `get_block_hash` actually indexes
        # into a list of prev_hashes. The 0th index is the hash of the previous block
        expected_hash = casper_chain.head_state.get_block_hash(0)

        assert current_epoch == next_epoch
        assert casper.checkpoint_hashes(current_epoch) == expected_hash


def test_checkpoint_deposits(casper_chain, casper, funded_privkeys, deposit_amount,
                             induct_validator, deposit_validator, new_epoch,
                             mk_suggested_vote):
    current_epoch = casper.current_epoch()
    assert casper.checkpoints__cur_dyn_deposits(current_epoch) == 0
    assert casper.checkpoints__prev_dyn_deposits(current_epoch) == 0

    new_epoch()
    current_epoch = casper.current_epoch()

    assert casper.checkpoints__cur_dyn_deposits(current_epoch) == 0
    assert casper.checkpoints__prev_dyn_deposits(current_epoch) == 0

    initial_validator = deposit_validator(funded_privkeys[0], deposit_amount)

    new_epoch()
    current_epoch = casper.current_epoch()

    assert casper.checkpoints__cur_dyn_deposits(current_epoch) == 0
    assert casper.checkpoints__prev_dyn_deposits(current_epoch) == 0

    new_epoch()
    current_epoch = casper.current_epoch()

    # checkpoints are for the last block in the previous epoch
    # so checkpoint dynasty totals should lag behind
    assert casper.total_curdyn_deposits_in_wei() == deposit_amount
    assert casper.total_prevdyn_deposits_in_wei() == 0
    assert casper.checkpoints__cur_dyn_deposits(current_epoch) == 0
    assert casper.checkpoints__prev_dyn_deposits(current_epoch) == 0

    casper.vote(mk_suggested_vote(initial_validator, funded_privkeys[0]))
    new_epoch()
    current_epoch = casper.current_epoch()

    assert casper.total_curdyn_deposits_in_wei() == deposit_amount
    assert casper.total_prevdyn_deposits_in_wei() == deposit_amount
    assert casper.checkpoints__cur_dyn_deposits(current_epoch) == deposit_amount
    assert casper.checkpoints__prev_dyn_deposits(current_epoch) == 0

    second_validator = deposit_validator(funded_privkeys[1], deposit_amount)

    casper.vote(mk_suggested_vote(initial_validator, funded_privkeys[0]))
    new_epoch()
    current_epoch = casper.current_epoch()

    assert casper.total_curdyn_deposits_in_wei() == deposit_amount
    assert casper.total_prevdyn_deposits_in_wei() == deposit_amount
    assert casper.checkpoints__cur_dyn_deposits(current_epoch) == deposit_amount
    assert casper.checkpoints__prev_dyn_deposits(current_epoch) == deposit_amount

    prev_curdyn_deposits = casper.total_curdyn_deposits_in_wei()
    prev_prevdyn_deposits = casper.total_prevdyn_deposits_in_wei()

    casper.vote(mk_suggested_vote(initial_validator, funded_privkeys[0]))
    new_epoch()
    current_epoch = casper.current_epoch()

    assert casper.checkpoints__cur_dyn_deposits(current_epoch) >= prev_curdyn_deposits \
        and casper.checkpoints__cur_dyn_deposits(current_epoch) < prev_curdyn_deposits * 1.01
    assert casper.checkpoints__prev_dyn_deposits(current_epoch) >= prev_prevdyn_deposits \
        and casper.checkpoints__prev_dyn_deposits(current_epoch) < prev_prevdyn_deposits * 1.01

    for _ in range(3):
        prev_curdyn_deposits = casper.total_curdyn_deposits_in_wei()
        prev_prevdyn_deposits = casper.total_prevdyn_deposits_in_wei()

        casper.vote(mk_suggested_vote(initial_validator, funded_privkeys[0]))
        casper.vote(mk_suggested_vote(second_validator, funded_privkeys[1]))
        new_epoch()
        current_epoch = casper.current_epoch()

        assert casper.checkpoints__cur_dyn_deposits(current_epoch) >= prev_curdyn_deposits \
            and casper.checkpoints__cur_dyn_deposits(current_epoch) < prev_curdyn_deposits * 1.01
        assert casper.checkpoints__prev_dyn_deposits(current_epoch) >= prev_prevdyn_deposits \
            and casper.checkpoints__prev_dyn_deposits(current_epoch) < prev_prevdyn_deposits * 1.01
