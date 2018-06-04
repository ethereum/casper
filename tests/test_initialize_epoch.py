import pytest

from web3 import (
    Web3,
)


# ensure that our fixture 'new_epoch' functions properly
@pytest.mark.parametrize(
    'warm_up_period, epoch_length',
    [
        (0, 5),
        (20, 10),
        (21, 10),
        (220, 20),
    ]
)
def test_new_epoch_fixture(tester, concise_casper, new_epoch, warm_up_period, epoch_length):
    for i in range(4):
        prev_epoch = concise_casper.current_epoch()
        prev_block_number = tester.get_block_by_number('latest')['number']
        if i == 0:
            expected_jump = warm_up_period
            expected_jump += epoch_length - (prev_block_number + warm_up_period) % epoch_length
        else:
            expected_jump = epoch_length - (prev_block_number % epoch_length)

        new_epoch()
        block_number = tester.get_block_by_number('latest')['number']

        assert concise_casper.current_epoch() == prev_epoch + 1

        # +1 because intialize_epoch is mined to take effect
        assert block_number == prev_block_number + expected_jump + 1
        # should be 1 block past the initialize_epoch block
        assert (block_number % epoch_length) == 1


def test_epoch_length_range(tester, casper, new_epoch, epoch_length, assert_tx_failed):
    new_epoch()

    for _ in range(epoch_length * 3):   # check the entire range 3 times
        block_number = tester.get_block_by_number('latest')['number']

        next_is_init_block = (block_number + 1) % epoch_length == 0
        next_epoch = casper.functions.current_epoch().call() + 1
        if next_is_init_block:
            casper.functions.initialize_epoch(next_epoch).transact()
            assert casper.functions.current_epoch().call() == next_epoch
        else:
            assert_tx_failed(
                lambda: casper.functions.initialize_epoch(next_epoch).transact()
            )
            tester.mine_block()


@pytest.mark.parametrize(
    'warm_up_period, epoch_length',
    [
        (15, 5),
        (20, 10),
        (100, 50),
        (220, 20),
    ]
)
def test_cannot_initialize_during_warm_up(
        tester,
        casper,
        epoch_length,
        warm_up_period,
        assert_tx_failed):

    block_number = tester.get_block_by_number('latest')['number']
    current_epoch = casper.functions.current_epoch().call()
    assert current_epoch == (block_number + warm_up_period) // epoch_length

    next_epoch = current_epoch + 1
    # -1 because the block that called 'init' counts toward warm_up_period
    for _ in range(warm_up_period - 1):
        # check then mine to ensure that the start block counts
        assert_tx_failed(
            lambda: casper.functions.initialize_epoch(next_epoch).transact()
        )
        tester.mine_block()

    # mine right up until the start of the next epoch
    next_block_number = tester.get_block_by_number('latest')['number'] + 1
    blocks_until_next_start = epoch_length - next_block_number % epoch_length
    for _ in range(blocks_until_next_start):
        assert_tx_failed(
            lambda: casper.functions.initialize_epoch(next_epoch).transact()
        )
        tester.mine_block()

    next_block_number = tester.get_block_by_number('latest')['number'] + 1
    assert next_block_number % epoch_length == 0
    # at start of next_epoch
    casper.functions.initialize_epoch(next_epoch).transact()
    assert casper.functions.current_epoch().call() == next_epoch


def test_double_epoch_initialization(tester, casper, new_epoch, epoch_length, assert_tx_failed):
    new_epoch()
    initial_epoch = casper.functions.current_epoch().call()

    tester.mine_blocks(epoch_length - 2)
    next_block_number = tester.get_block_by_number('latest')['number'] + 1
    assert next_block_number % epoch_length == 0

    next_epoch = initial_epoch + 1
    casper.functions.initialize_epoch(next_epoch).transact()
    assert casper.functions.current_epoch().call() == next_epoch
    assert_tx_failed(
        lambda: casper.functions.initialize_epoch(next_epoch).transact()
    )


def test_epoch_initialization_one_block_late(tester, casper, epoch_length, new_epoch):
    new_epoch()
    initial_epoch = casper.functions.current_epoch().call()

    tester.mine_blocks(epoch_length - 1)
    next_block_number = tester.get_block_by_number('latest')['number'] + 1
    assert (next_block_number % epoch_length) == 1

    expected_epoch = initial_epoch + 1
    casper.functions.initialize_epoch(expected_epoch).transact()

    assert casper.functions.current_epoch().call() == expected_epoch


def test_epoch_initialize_one_epoch_late(
        tester,
        casper,
        new_epoch,
        epoch_length,
        assert_tx_failed):
    new_epoch()
    initial_epoch = casper.functions.current_epoch().call()

    tester.mine_blocks(epoch_length * 2 - 2)
    next_block_number = tester.get_block_by_number('latest')['number'] + 1
    assert (next_block_number % epoch_length) == 0

    assert_tx_failed(
        lambda: casper.functions.initialize_epoch(initial_epoch + 2).transact()
    )
    assert casper.functions.current_epoch().call() == initial_epoch
    casper.functions.initialize_epoch(initial_epoch + 1).transact()
    assert casper.functions.current_epoch().call() == initial_epoch + 1
    casper.functions.initialize_epoch(initial_epoch + 2).transact()
    assert casper.functions.current_epoch().call() == initial_epoch + 2


def test_checkpoint_hashes(tester, casper, epoch_length, new_epoch):
    for _ in range(4):
        next_epoch = casper.functions.current_epoch().call() + 1

        block_number = tester.get_block_by_number('latest')['number']
        tester.mine_blocks(epoch_length * next_epoch - block_number - 1)

        next_block_number = tester.get_block_by_number('latest')['number'] + 1
        assert (next_block_number % epoch_length) == 0

        casper.functions.initialize_epoch(next_epoch).transact()
        current_epoch = casper.functions.current_epoch().call()

        checkpoint_block_number = next_block_number - 1
        expected_hash = tester.get_block_by_number(checkpoint_block_number)['hash']
        actual_hash = Web3.toHex(casper.functions.checkpoint_hashes(current_epoch).call())

        assert current_epoch == next_epoch
        assert actual_hash == expected_hash


def test_checkpoint_deposits(
        tester,
        casper,
        concise_casper,
        funded_accounts,
        validation_keys,
        deposit_amount,
        deposit_validator,
        new_epoch,
        send_vote,
        mk_suggested_vote):
    current_epoch = concise_casper.current_epoch()
    assert concise_casper.checkpoints__cur_dyn_deposits(current_epoch) == 0
    assert concise_casper.checkpoints__prev_dyn_deposits(current_epoch) == 0

    new_epoch()
    current_epoch = concise_casper.current_epoch()

    assert concise_casper.checkpoints__cur_dyn_deposits(current_epoch) == 0
    assert concise_casper.checkpoints__prev_dyn_deposits(current_epoch) == 0

    initial_validator = deposit_validator(funded_accounts[0], validation_keys[0], deposit_amount)

    new_epoch()
    current_epoch = concise_casper.current_epoch()

    assert concise_casper.checkpoints__cur_dyn_deposits(current_epoch) == 0
    assert concise_casper.checkpoints__prev_dyn_deposits(current_epoch) == 0

    new_epoch()
    current_epoch = concise_casper.current_epoch()

    # checkpoints are for the last block in the previous epoch
    # so checkpoint dynasty totals should lag behind
    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount
    assert concise_casper.total_prevdyn_deposits_in_wei() == 0
    assert concise_casper.checkpoints__cur_dyn_deposits(current_epoch) == 0
    assert concise_casper.checkpoints__prev_dyn_deposits(current_epoch) == 0

    send_vote(mk_suggested_vote(initial_validator, validation_keys[0]))
    new_epoch()
    current_epoch = concise_casper.current_epoch()

    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount
    assert concise_casper.total_prevdyn_deposits_in_wei() == deposit_amount
    assert concise_casper.checkpoints__cur_dyn_deposits(current_epoch) == deposit_amount
    assert concise_casper.checkpoints__prev_dyn_deposits(current_epoch) == 0

    second_validator = deposit_validator(funded_accounts[1], validation_keys[1], deposit_amount)

    send_vote(mk_suggested_vote(initial_validator, validation_keys[0]))
    new_epoch()
    current_epoch = concise_casper.current_epoch()

    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount
    assert concise_casper.total_prevdyn_deposits_in_wei() == deposit_amount
    assert concise_casper.checkpoints__cur_dyn_deposits(current_epoch) == deposit_amount
    assert concise_casper.checkpoints__prev_dyn_deposits(current_epoch) == deposit_amount

    prev_curdyn_deposits = concise_casper.total_curdyn_deposits_in_wei()
    prev_prevdyn_deposits = concise_casper.total_prevdyn_deposits_in_wei()

    send_vote(mk_suggested_vote(initial_validator, validation_keys[0]))
    new_epoch()
    current_epoch = concise_casper.current_epoch()

    cur_dyn_deposits = concise_casper.checkpoints__cur_dyn_deposits(current_epoch)
    prev_dyn_deposits = concise_casper.checkpoints__prev_dyn_deposits(current_epoch)
    assert cur_dyn_deposits >= prev_curdyn_deposits \
        and cur_dyn_deposits < prev_curdyn_deposits * 1.01
    assert prev_dyn_deposits >= prev_prevdyn_deposits \
        and prev_dyn_deposits < prev_prevdyn_deposits * 1.01

    for _ in range(3):
        prev_curdyn_deposits = concise_casper.total_curdyn_deposits_in_wei()
        prev_prevdyn_deposits = concise_casper.total_prevdyn_deposits_in_wei()

        send_vote(mk_suggested_vote(initial_validator, validation_keys[0]))
        send_vote(mk_suggested_vote(second_validator, validation_keys[1]))
        new_epoch()
        current_epoch = concise_casper.current_epoch()

        cur_dyn_deposits = concise_casper.checkpoints__cur_dyn_deposits(current_epoch)
        prev_dyn_deposits = concise_casper.checkpoints__prev_dyn_deposits(current_epoch)

        assert cur_dyn_deposits >= prev_curdyn_deposits \
            and cur_dyn_deposits < prev_curdyn_deposits * 1.01
        assert prev_dyn_deposits >= prev_prevdyn_deposits \
            and prev_dyn_deposits < prev_prevdyn_deposits * 1.01
