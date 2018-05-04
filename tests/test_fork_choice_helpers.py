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


def test_highest_justified_epoch(casper, funded_privkey, deposit_amount,
                                 new_epoch, induct_validator, mk_suggested_vote):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.total_curdyn_deposits_scaled() == deposit_amount
    assert casper.current_epoch() == 3

    assert casper.highest_justified_epoch(deposit_amount) == 0
    assert casper.highest_justified_epoch(0) == 2

    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    assert casper.checkpoints__cur_dyn_deposits(3) == 0
    assert casper.checkpoints__prev_dyn_deposits(3) == 0
    assert casper.last_justified_epoch() == 3

    assert casper.highest_justified_epoch(deposit_amount) == 0

    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    assert casper.checkpoints__cur_dyn_deposits(4) == deposit_amount
    assert casper.checkpoints__prev_dyn_deposits(4) == 0
    assert casper.last_justified_epoch() == 4

    assert casper.highest_justified_epoch(deposit_amount) == 0
    assert casper.highest_justified_epoch(0) == 4

    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    assert casper.checkpoints__cur_dyn_deposits(5) == deposit_amount
    assert casper.checkpoints__prev_dyn_deposits(5) == deposit_amount
    assert casper.last_justified_epoch() == 5

    assert casper.highest_justified_epoch(deposit_amount) == 5
    assert casper.highest_justified_epoch(0) == 5
    assert casper.highest_justified_epoch(deposit_amount*2) == 0

    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    assert casper.checkpoints__cur_dyn_deposits(6) > deposit_amount
    assert casper.checkpoints__prev_dyn_deposits(6) > deposit_amount
    assert casper.last_justified_epoch() == 6

    assert casper.highest_justified_epoch(deposit_amount) == 6
    assert casper.highest_justified_epoch(int(deposit_amount * 1.1)) == 0
    assert casper.highest_justified_epoch(0) == 6

    new_epoch()
    # no vote

    assert casper.checkpoints__cur_dyn_deposits(6) > deposit_amount
    assert casper.checkpoints__prev_dyn_deposits(6) > deposit_amount
    assert casper.last_justified_epoch() == 6

    assert casper.highest_justified_epoch(deposit_amount) == 6
    assert casper.highest_justified_epoch(0) == 6

    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    assert casper.checkpoints__cur_dyn_deposits(8) > deposit_amount
    assert casper.checkpoints__prev_dyn_deposits(8) > deposit_amount
    assert casper.last_justified_epoch() == 8

    assert casper.highest_justified_epoch(deposit_amount) == 8
    assert casper.highest_justified_epoch(0) == 8
    assert casper.highest_justified_epoch(int(deposit_amount * 1.1)) == 0
