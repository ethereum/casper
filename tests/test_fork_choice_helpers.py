import pytest


@pytest.mark.parametrize(
    'start_epoch,min_deposits',
    [
        (2, 0),
        (3, 1),
        (0, int(1e4)),
        (7, int(4e10)),
        (6, int(2e30))
    ]
)
def test_default_highest_justified_epoch(test_chain, start_epoch, min_deposits, epoch_length,
                                         casper_args, deploy_casper_contract):
    test_chain.mine(
        epoch_length * start_epoch - test_chain.head_state.block_number
    )
    casper = deploy_casper_contract(casper_args)

    assert casper.highest_justified_epoch(min_deposits) == 0


@pytest.mark.parametrize(
    'min_deposits',
    [
        (0),
        (1),
        (int(1e4)),
        (int(4e10)),
        (int(2e30))
    ]
)
def test_highest_justified_epoch_no_validators(casper, new_epoch, min_deposits):
    for i in range(5):
        highest_justified_epoch = casper.highest_justified_epoch(min_deposits)
        if min_deposits == 0:
            assert highest_justified_epoch == casper.last_justified_epoch()
        else:
            assert highest_justified_epoch == 0

        new_epoch()


@pytest.mark.parametrize(
    'start_epoch,min_deposits',
    [
        (2, 0),
        (3, 1),
        (0, int(1e4)),
        (7, int(4e10)),
        (6, int(2e30))
    ]
)
def test_default_highest_finalized_epoch(test_chain, start_epoch, min_deposits, epoch_length,
                                         casper_args, deploy_casper_contract):
    test_chain.mine(
        epoch_length * start_epoch - test_chain.head_state.block_number
    )
    casper = deploy_casper_contract(casper_args)

    assert casper.highest_finalized_epoch(min_deposits) == -1


@pytest.mark.parametrize(
    'min_deposits',
    [
        (0),
        (1),
        (int(1e4)),
        (int(4e10)),
        (int(2e30))
    ]
)
def test_highest_finalized_epoch_no_validators(casper, new_epoch, min_deposits):
    for i in range(5):
        highest_finalized_epoch = casper.highest_finalized_epoch(min_deposits)
        if min_deposits > 0:
            expected_epoch = -1
        else:
            if casper.current_epoch() == casper.START_EPOCH():
                expected_epoch = -1
            else:
                expected_epoch = casper.last_finalized_epoch()

        assert highest_finalized_epoch == expected_epoch

        new_epoch()


def test_highest_justified_and_epoch(casper, funded_privkey, deposit_amount,
                                     new_epoch, induct_validator, mk_suggested_vote):
    start_epoch = casper.START_EPOCH()
    validator_index = induct_validator(funded_privkey, deposit_amount)
    higher_deposit = int(deposit_amount * 1.1)

    assert casper.total_curdyn_deposits_in_wei() == deposit_amount
    assert casper.current_epoch() == start_epoch + 3  # 3 to induct first dynasty

    assert casper.highest_justified_epoch(deposit_amount) == 0
    assert casper.highest_finalized_epoch(deposit_amount) == -1
    assert casper.highest_justified_epoch(0) == start_epoch + 2
    assert casper.highest_finalized_epoch(0) == start_epoch + 2
    assert casper.highest_justified_epoch(higher_deposit) == 0
    assert casper.highest_finalized_epoch(higher_deposit) == -1

    # justify current_epoch in contract
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    assert casper.checkpoints__cur_dyn_deposits(start_epoch + 3) == 0
    assert casper.checkpoints__prev_dyn_deposits(start_epoch + 3) == 0
    assert casper.last_justified_epoch() == start_epoch + 3
    assert casper.last_finalized_epoch() == start_epoch + 2

    assert casper.highest_justified_epoch(deposit_amount) == 0
    assert casper.highest_finalized_epoch(deposit_amount) == -1
    assert casper.highest_justified_epoch(0) == start_epoch + 3
    assert casper.highest_finalized_epoch(0) == start_epoch + 2
    assert casper.highest_justified_epoch(higher_deposit) == 0
    assert casper.highest_finalized_epoch(higher_deposit) == -1

    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    assert casper.checkpoints__cur_dyn_deposits(start_epoch + 4) == deposit_amount
    assert casper.checkpoints__prev_dyn_deposits(start_epoch + 4) == 0
    assert casper.last_justified_epoch() == start_epoch + 4
    assert casper.last_finalized_epoch() == start_epoch + 3

    assert casper.highest_justified_epoch(deposit_amount) == 0
    assert casper.highest_finalized_epoch(deposit_amount) == -1
    assert casper.highest_justified_epoch(0) == start_epoch + 4
    assert casper.highest_finalized_epoch(0) == start_epoch + 3
    assert casper.highest_justified_epoch(higher_deposit) == 0
    assert casper.highest_finalized_epoch(higher_deposit) == -1

    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    assert casper.checkpoints__cur_dyn_deposits(start_epoch + 5) == deposit_amount
    assert casper.checkpoints__prev_dyn_deposits(start_epoch + 5) == deposit_amount
    assert casper.last_justified_epoch() == start_epoch + 5
    assert casper.last_finalized_epoch() == start_epoch + 4

    # enough prev and cur deposits in checkpoint 5 for the justified block
    assert casper.highest_justified_epoch(deposit_amount) == start_epoch + 5
    # not enough prev and cur deposits in checkpoint 4 for the finalized block
    assert casper.highest_finalized_epoch(deposit_amount) == -1
    assert casper.highest_justified_epoch(0) == start_epoch + 5
    assert casper.highest_finalized_epoch(0) == start_epoch + 4
    assert casper.highest_justified_epoch(higher_deposit) == 0
    assert casper.highest_finalized_epoch(higher_deposit) == -1

    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    assert casper.checkpoints__cur_dyn_deposits(start_epoch + 6) > deposit_amount
    assert casper.checkpoints__prev_dyn_deposits(start_epoch + 6) > deposit_amount
    assert casper.last_justified_epoch() == start_epoch + 6
    assert casper.last_finalized_epoch() == start_epoch + 5

    # enough deposits in checkpoint 6 for justified and checkpoint 5 for finalized!
    assert casper.highest_justified_epoch(deposit_amount) == start_epoch + 6
    assert casper.highest_finalized_epoch(deposit_amount) == start_epoch + 5
    assert casper.highest_justified_epoch(higher_deposit) == 0
    assert casper.highest_finalized_epoch(higher_deposit) == -1
    assert casper.highest_justified_epoch(0) == start_epoch + 6
    assert casper.highest_finalized_epoch(0) == start_epoch + 5

    new_epoch()
    # no vote

    assert casper.checkpoints__cur_dyn_deposits(start_epoch + 7) > deposit_amount
    assert casper.checkpoints__prev_dyn_deposits(start_epoch + 7) > deposit_amount
    assert casper.last_justified_epoch() == start_epoch + 6
    assert casper.last_finalized_epoch() == start_epoch + 5

    assert casper.highest_justified_epoch(deposit_amount) == start_epoch + 6
    assert casper.highest_finalized_epoch(deposit_amount) == start_epoch + 5
    assert casper.highest_justified_epoch(0) == start_epoch + 6
    assert casper.highest_finalized_epoch(0) == start_epoch + 5
    assert casper.highest_justified_epoch(higher_deposit) == 0
    assert casper.highest_finalized_epoch(higher_deposit) == -1

    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    assert casper.checkpoints__cur_dyn_deposits(start_epoch + 8) > deposit_amount
    assert casper.checkpoints__prev_dyn_deposits(start_epoch + 8) > deposit_amount
    # new justified
    assert casper.last_justified_epoch() == start_epoch + 8
    # no new finalized because not sequential justified blocks
    assert casper.last_finalized_epoch() == start_epoch + 5

    assert casper.highest_justified_epoch(deposit_amount) == start_epoch + 8
    assert casper.highest_finalized_epoch(deposit_amount) == start_epoch + 5
    assert casper.highest_justified_epoch(0) == start_epoch + 8
    assert casper.highest_finalized_epoch(0) == start_epoch + 5
    assert casper.highest_justified_epoch(higher_deposit) == 0
    assert casper.highest_finalized_epoch(higher_deposit) == -1

    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    assert casper.checkpoints__cur_dyn_deposits(9) > deposit_amount
    assert casper.checkpoints__prev_dyn_deposits(9) > deposit_amount
    # new justified and finalized because sequential justified blocks
    assert casper.last_justified_epoch() == start_epoch + 9
    assert casper.last_finalized_epoch() == start_epoch + 8

    assert casper.highest_justified_epoch(deposit_amount) == start_epoch + 9
    assert casper.highest_finalized_epoch(deposit_amount) == start_epoch + 8
    assert casper.highest_justified_epoch(0) == start_epoch + 9
    assert casper.highest_finalized_epoch(0) == start_epoch + 8
    assert casper.highest_justified_epoch(higher_deposit) == 0
    assert casper.highest_finalized_epoch(higher_deposit) == -1
