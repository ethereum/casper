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
def test_default_highest_justified_epoch(
        base_tester,
        start_epoch,
        min_deposits,
        epoch_length,
        casper_args,
        deploy_casper_contract):
    block_number = base_tester.get_block_by_number('latest')['number']
    base_tester.mine_blocks(
        epoch_length * start_epoch - block_number
    )
    casper = deploy_casper_contract(casper_args)

    assert casper.functions.highest_justified_epoch(min_deposits).call() == 0


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
def test_highest_justified_epoch_no_validators(
        concise_casper,
        new_epoch,
        min_deposits):
    for i in range(5):
        highest_justified_epoch = concise_casper.highest_justified_epoch(min_deposits)
        if min_deposits == 0:
            assert highest_justified_epoch == concise_casper.last_justified_epoch()
        else:
            assert highest_justified_epoch == 0

        new_epoch()


@pytest.mark.parametrize(
    'start_epoch,min_deposits,warm_up_period',
    [
        (2, 0, 0),
        (3, 1, 0),
        (0, int(1e4), 0),
        (7, int(4e10), 0),
        (6, int(2e30), 0),
    ]
)
def test_default_highest_finalized_epoch(
        base_tester,
        start_epoch,
        min_deposits,
        warm_up_period,
        epoch_length,
        casper_args,
        deploy_casper_contract):

    block_number = base_tester.get_block_by_number('latest')['number']
    base_tester.mine_blocks(
        max(epoch_length * start_epoch - block_number - 2, 0)
    )
    casper = deploy_casper_contract(casper_args)

    assert casper.functions.START_EPOCH().call() == start_epoch
    assert casper.functions.highest_finalized_epoch(min_deposits).call() == -1


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
def test_highest_finalized_epoch_no_validators(concise_casper, new_epoch, min_deposits):
    for i in range(5):
        highest_finalized_epoch = concise_casper.highest_finalized_epoch(min_deposits)
        if min_deposits > 0:
            expected_epoch = -1
        else:
            if concise_casper.current_epoch() == concise_casper.START_EPOCH():
                expected_epoch = -1
            else:
                expected_epoch = concise_casper.last_finalized_epoch()

        assert highest_finalized_epoch == expected_epoch

        new_epoch()


def test_highest_justified_and_epoch(
        casper,
        concise_casper,
        funded_account,
        validation_key,
        deposit_amount,
        new_epoch,
        induct_validator,
        send_vote,
        mk_suggested_vote):
    start_epoch = concise_casper.START_EPOCH()
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)
    higher_deposit = int(deposit_amount * 1.1)

    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount
    assert concise_casper.current_epoch() == start_epoch + 3  # 3 to induct first dynasty

    assert concise_casper.highest_justified_epoch(deposit_amount) == 0
    assert concise_casper.highest_finalized_epoch(deposit_amount) == -1
    assert concise_casper.highest_justified_epoch(0) == start_epoch + 2
    assert concise_casper.highest_finalized_epoch(0) == start_epoch + 2
    assert concise_casper.highest_justified_epoch(higher_deposit) == 0
    assert concise_casper.highest_finalized_epoch(higher_deposit) == -1

    # justify current_epoch in contract
    send_vote(mk_suggested_vote(validator_index, validation_key))

    assert concise_casper.checkpoints__cur_dyn_deposits(start_epoch + 3) == 0
    assert concise_casper.checkpoints__prev_dyn_deposits(start_epoch + 3) == 0
    assert concise_casper.last_justified_epoch() == start_epoch + 3
    assert concise_casper.last_finalized_epoch() == start_epoch + 2

    assert concise_casper.highest_justified_epoch(deposit_amount) == 0
    assert concise_casper.highest_finalized_epoch(deposit_amount) == -1
    assert concise_casper.highest_justified_epoch(0) == start_epoch + 3
    assert concise_casper.highest_finalized_epoch(0) == start_epoch + 2
    assert concise_casper.highest_justified_epoch(higher_deposit) == 0
    assert concise_casper.highest_finalized_epoch(higher_deposit) == -1

    new_epoch()
    send_vote(mk_suggested_vote(validator_index, validation_key))

    assert concise_casper.checkpoints__cur_dyn_deposits(start_epoch + 4) == deposit_amount
    assert concise_casper.checkpoints__prev_dyn_deposits(start_epoch + 4) == 0
    assert concise_casper.last_justified_epoch() == start_epoch + 4
    assert concise_casper.last_finalized_epoch() == start_epoch + 3

    assert concise_casper.highest_justified_epoch(deposit_amount) == 0
    assert concise_casper.highest_finalized_epoch(deposit_amount) == -1
    assert concise_casper.highest_justified_epoch(0) == start_epoch + 4
    assert concise_casper.highest_finalized_epoch(0) == start_epoch + 3
    assert concise_casper.highest_justified_epoch(higher_deposit) == 0
    assert concise_casper.highest_finalized_epoch(higher_deposit) == -1

    new_epoch()
    send_vote(mk_suggested_vote(validator_index, validation_key))

    assert concise_casper.checkpoints__cur_dyn_deposits(start_epoch + 5) == deposit_amount
    assert concise_casper.checkpoints__prev_dyn_deposits(start_epoch + 5) == deposit_amount
    assert concise_casper.last_justified_epoch() == start_epoch + 5
    assert concise_casper.last_finalized_epoch() == start_epoch + 4

    # enough prev and cur deposits in checkpoint 5 for the justified block
    assert concise_casper.highest_justified_epoch(deposit_amount) == start_epoch + 5
    # not enough prev and cur deposits in checkpoint 4 for the finalized block
    assert concise_casper.highest_finalized_epoch(deposit_amount) == -1
    assert concise_casper.highest_justified_epoch(0) == start_epoch + 5
    assert concise_casper.highest_finalized_epoch(0) == start_epoch + 4
    assert concise_casper.highest_justified_epoch(higher_deposit) == 0
    assert concise_casper.highest_finalized_epoch(higher_deposit) == -1

    new_epoch()
    send_vote(mk_suggested_vote(validator_index, validation_key))

    assert concise_casper.checkpoints__cur_dyn_deposits(start_epoch + 6) > deposit_amount
    assert concise_casper.checkpoints__prev_dyn_deposits(start_epoch + 6) > deposit_amount
    assert concise_casper.last_justified_epoch() == start_epoch + 6
    assert concise_casper.last_finalized_epoch() == start_epoch + 5

    # enough deposits in checkpoint 6 for justified and checkpoint 5 for finalized!
    assert concise_casper.highest_justified_epoch(deposit_amount) == start_epoch + 6
    assert concise_casper.highest_finalized_epoch(deposit_amount) == start_epoch + 5
    assert concise_casper.highest_justified_epoch(higher_deposit) == 0
    assert concise_casper.highest_finalized_epoch(higher_deposit) == -1
    assert concise_casper.highest_justified_epoch(0) == start_epoch + 6
    assert concise_casper.highest_finalized_epoch(0) == start_epoch + 5

    new_epoch()
    # no vote

    assert concise_casper.checkpoints__cur_dyn_deposits(start_epoch + 7) > deposit_amount
    assert concise_casper.checkpoints__prev_dyn_deposits(start_epoch + 7) > deposit_amount
    assert concise_casper.last_justified_epoch() == start_epoch + 6
    assert concise_casper.last_finalized_epoch() == start_epoch + 5

    assert concise_casper.highest_justified_epoch(deposit_amount) == start_epoch + 6
    assert concise_casper.highest_finalized_epoch(deposit_amount) == start_epoch + 5
    assert concise_casper.highest_justified_epoch(0) == start_epoch + 6
    assert concise_casper.highest_finalized_epoch(0) == start_epoch + 5
    assert concise_casper.highest_justified_epoch(higher_deposit) == 0
    assert concise_casper.highest_finalized_epoch(higher_deposit) == -1

    new_epoch()
    send_vote(mk_suggested_vote(validator_index, validation_key))

    assert concise_casper.checkpoints__cur_dyn_deposits(start_epoch + 8) > deposit_amount
    assert concise_casper.checkpoints__prev_dyn_deposits(start_epoch + 8) > deposit_amount
    # new justified
    assert concise_casper.last_justified_epoch() == start_epoch + 8
    # no new finalized because not sequential justified blocks
    assert concise_casper.last_finalized_epoch() == start_epoch + 5

    assert concise_casper.highest_justified_epoch(deposit_amount) == start_epoch + 8
    assert concise_casper.highest_finalized_epoch(deposit_amount) == start_epoch + 5
    assert concise_casper.highest_justified_epoch(0) == start_epoch + 8
    assert concise_casper.highest_finalized_epoch(0) == start_epoch + 5
    assert concise_casper.highest_justified_epoch(higher_deposit) == 0
    assert concise_casper.highest_finalized_epoch(higher_deposit) == -1

    new_epoch()
    send_vote(mk_suggested_vote(validator_index, validation_key))

    assert concise_casper.checkpoints__cur_dyn_deposits(9) > deposit_amount
    assert concise_casper.checkpoints__prev_dyn_deposits(9) > deposit_amount
    # new justified and finalized because sequential justified blocks
    assert concise_casper.last_justified_epoch() == start_epoch + 9
    assert concise_casper.last_finalized_epoch() == start_epoch + 8

    assert concise_casper.highest_justified_epoch(deposit_amount) == start_epoch + 9
    assert concise_casper.highest_finalized_epoch(deposit_amount) == start_epoch + 8
    assert concise_casper.highest_justified_epoch(0) == start_epoch + 9
    assert concise_casper.highest_finalized_epoch(0) == start_epoch + 8
    assert concise_casper.highest_justified_epoch(higher_deposit) == 0
    assert concise_casper.highest_finalized_epoch(higher_deposit) == -1
