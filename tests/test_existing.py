import pytest

from ethereum import utils
from ethereum.tools import tester


def test_init_first_epoch(casper, new_epoch):
    assert casper.current_epoch() == 0
    assert casper.nextValidatorIndex() == 1

    new_epoch()

    assert casper.dynasty() == 0
    assert casper.nextValidatorIndex() == 1
    assert casper.current_epoch() == 1


@pytest.mark.parametrize(
    'privkey, amount, success',
    [
        (tester.k1, 2000 * 10**18, True),
        (tester.k1, 1000 * 10**18, True),
        (tester.k2, 1500 * 10**18, True),
        (tester.k1, 999 * 10**18, False),
        (tester.k1, 10 * 10**18, False),
    ]
)
def test_deposit(casper_chain, casper, privkey, amount,
                 success, induct_validator, new_epoch, assert_tx_failed):
    assert casper.current_epoch() == 0
    assert casper.nextValidatorIndex() == 1

    if not success:
        assert_tx_failed(lambda: induct_validator(privkey, amount))
        return

    induct_validator(privkey, amount)

    assert casper.nextValidatorIndex() == 2
    assert casper.validator_indexes(utils.privtoaddr(privkey)) == 1
    assert casper.get_deposit_size(1) == amount

    for i in range(3):
        new_epoch()

    assert casper.dynasty() == 2
    assert casper.get_total_curdyn_deposits() == amount
    assert casper.get_total_prevdyn_deposits() == 0


@pytest.mark.parametrize(
    'privkey, amount',
    [
        (tester.k1, 2000 * 10**18),
        (tester.k1, 1000 * 10**18),
        (tester.k2, 1500 * 10**18),
    ]
)
def test_vote_single_validator(casper, privkey, amount,
                               new_epoch, induct_validator, mk_suggested_vote):
    # induct validator and step forward two dynasties
    validator_index = casper.nextValidatorIndex()
    induct_validator(privkey, amount)
    for i in range(3):
        new_epoch()
    assert casper.get_total_curdyn_deposits() == amount

    prev_dynasty = casper.dynasty()
    for i in range(10):
        casper.vote(mk_suggested_vote(validator_index, privkey))
        assert casper.main_hash_justified()
        assert casper.votes__is_finalized(casper.get_recommended_source_epoch())
        new_epoch()
        assert casper.dynasty() == prev_dynasty + 1
        prev_dynasty += 1


@pytest.mark.parametrize(
    'privkey, amount',
    [
        (tester.k1, 2000 * 10**18),
        (tester.k1, 1000 * 10**18),
        (tester.k2, 1500 * 10**18),
    ]
)
def test_vote_target_epoch_twice(casper, privkey, amount, new_epoch,
                                 induct_validator, mk_suggested_vote, assert_tx_failed):
    # induct validator and step forward two dynasties
    validator_index = casper.nextValidatorIndex()
    induct_validator(privkey, amount)
    for i in range(3):
        new_epoch()
    assert casper.get_total_curdyn_deposits() == amount

    casper.vote(mk_suggested_vote(validator_index, privkey))
    # second vote on same target epoch fails
    assert_tx_failed(lambda: casper.vote(mk_suggested_vote(validator_index, privkey)))


@pytest.mark.parametrize(
    'privkey, amount',
    [
        (tester.k1, 2000 * 10**18),
        (tester.k1, 1000 * 10**18),
        (tester.k2, 1500 * 10**18),
    ]
)
def test_non_finalization_loss(casper, privkey, amount, new_epoch,
                               induct_validator, mk_suggested_vote, assert_tx_failed):
    # induct validator and step forward two dynasties
    validator_index = casper.nextValidatorIndex()
    induct_validator(privkey, amount)
    for i in range(3):
        new_epoch()
    assert casper.get_total_curdyn_deposits() == amount

    casper.vote(mk_suggested_vote(validator_index, privkey))
    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, privkey))
    new_epoch()

    ds_prev_non_finalized = casper.get_deposit_size(validator_index)
    for i in range(5):
        new_epoch()
        ds_cur_non_finalized = casper.get_deposit_size(validator_index)
        assert ds_cur_non_finalized < ds_prev_non_finalized
        ds_prev_non_finalized = ds_cur_non_finalized
