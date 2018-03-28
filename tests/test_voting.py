import pytest

from ethereum import utils
from ethereum.tools import tester


@pytest.mark.parametrize(
    'privkey, amount, success',
    [
        (tester.k1, 2000 * 10**18, True),
        (tester.k1, 1000 * 10**18, True),
        (tester.k2, 1500 * 10**18, True),

        # below min_deposit_size
        (tester.k1, 999 * 10**18, False),
        (tester.k1, 10 * 10**18, False),
    ]
)
def test_deposit(casper_chain, casper, privkey, amount,
                 success, deposit_validator, new_epoch, assert_tx_failed):
    new_epoch()
    assert casper.get_current_epoch() == 1
    assert casper.get_nextValidatorIndex() == 1

    if not success:
        assert_tx_failed(lambda: deposit_validator(privkey, amount))
        return

    deposit_validator(privkey, amount)

    assert casper.get_nextValidatorIndex() == 2
    assert casper.get_validator_indexes(utils.privtoaddr(privkey)) == 1
    assert casper.get_deposit_size(1) == amount

    for i in range(2):
        new_epoch()

    assert casper.get_dynasty() == 2
    assert casper.get_total_curdyn_deposits() == amount
    assert casper.get_total_prevdyn_deposits() == 0


def test_vote_single_validator(casper, funded_privkey, deposit_amount,
                               new_epoch, induct_validator, mk_suggested_vote):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.get_total_curdyn_deposits() == deposit_amount

    prev_dynasty = casper.get_dynasty()
    for i in range(10):
        casper.vote(mk_suggested_vote(validator_index, funded_privkey))
        assert casper.get_main_hash_justified()
        assert casper.get_votes__is_finalized(casper.get_recommended_source_epoch())
        new_epoch()
        assert casper.get_dynasty() == prev_dynasty + 1
        prev_dynasty += 1


def test_vote_target_epoch_twice(casper, funded_privkey, deposit_amount, new_epoch,
                                 induct_validator, mk_suggested_vote, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.get_total_curdyn_deposits() == deposit_amount

    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    # second vote on same target epoch fails
    assert_tx_failed(lambda: casper.vote(mk_suggested_vote(validator_index, funded_privkey)))


def test_non_finalization_loss(casper, funded_privkey, deposit_amount, new_epoch,
                               induct_validator, mk_suggested_vote, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.get_total_curdyn_deposits() == deposit_amount

    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()

    ds_prev_non_finalized = casper.get_deposit_size(validator_index)
    for i in range(5):
        new_epoch()
        ds_cur_non_finalized = casper.get_deposit_size(validator_index)
        assert ds_cur_non_finalized < ds_prev_non_finalized
        ds_prev_non_finalized = ds_cur_non_finalized


def test_mismatched_epoch_and_hash(casper, funded_privkey, deposit_amount,
                                   induct_validator, mk_vote, new_epoch, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.get_total_curdyn_deposits() == deposit_amount

    # step forward one epoch to ensure that validator is allowed
    # to vote on (current_epoch - 1)
    new_epoch()

    target_hash = casper.get_recommended_target_hash()
    mismatched_target_epoch = casper.get_current_epoch() - 1
    source_epoch = casper.get_recommended_source_epoch()

    mismatched_vote = mk_vote(
        validator_index,
        target_hash,
        mismatched_target_epoch,
        source_epoch,
        funded_privkey
    )

    assert_tx_failed(lambda: casper.vote(mismatched_vote))


def test_consensus_after_non_finalization_streak(casper, funded_privkey, deposit_amount, new_epoch,
                                                 induct_validator, mk_suggested_vote,
                                                 assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.get_total_curdyn_deposits() == deposit_amount

    # finalize an epoch as a base to the test
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()

    # step forward 5 epochs without finalization
    for i in range(5):
        new_epoch()

    assert not casper.get_main_hash_justified()
    assert not casper.get_votes__is_finalized(casper.get_recommended_source_epoch())

    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    assert casper.get_main_hash_justified()
    assert not casper.get_votes__is_finalized(casper.get_recommended_source_epoch())

    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    assert casper.get_main_hash_justified()
    assert casper.get_votes__is_finalized(casper.get_recommended_source_epoch())


def test_logs(casper, funded_privkey, new_epoch, get_logs, deposit_validator,
              mk_suggested_vote, get_last_log, casper_chain, logout_validator):
    validator_index = casper.get_nextValidatorIndex()
    deposit_validator(funded_privkey, 1900 * 10 ** 18)
    # Deposit log
    log1 = get_last_log(casper_chain, casper)
    assert set(('_from', '_validation_address', '_validator_index', '_start_dyn', '_amount', '_event_type')) == log1.keys()
    assert log1['_event_type'] == b'Deposit'
    assert log1['_from'] == '0x' + utils.encode_hex(utils.privtoaddr(funded_privkey))
    assert log1['_validator_index'] == validator_index

    new_epoch()
    # Test epoch logs
    receipt = casper_chain.head_state.receipts[-1]
    logs = get_logs(receipt, casper)
    log_old = logs[-2]
    log_new = logs[-1]

    assert set(('_number', '_checkpoint_hash', '_is_justified', '_is_finalized', '_event_type')) == log_old.keys()
    # New epoch log
    assert log_new['_event_type'] == b'Epoch'
    assert log_new['_number'] == 1
    assert log_new['_is_justified'] is False
    assert log_new['_is_finalized'] is False
    # Insta finalized previous
    assert log_old['_event_type'] == b'Epoch'
    assert log_old['_number'] == 0
    assert log_old['_is_justified'] is True
    assert log_old['_is_finalized'] is True

    new_epoch()
    new_epoch()

    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    # vote log
    log2 = get_last_log(casper_chain, casper)
    assert set(('_from', '_validator_index', '_target_hash', '_target_epoch', '_source_epoch', '_event_type')) == log2.keys()
    assert log2['_event_type'] == b'Vote'
    assert log2['_from'] == '0x' + utils.encode_hex(utils.privtoaddr(funded_privkey))

    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    log3 = get_last_log(casper_chain, casper)
    assert log3['_event_type'] == b'Vote'

    logout_validator(validator_index, funded_privkey)
    # Logout log
    log4 = get_last_log(casper_chain, casper)
    assert set(('_from', '_validator_index', '_end_dyn', '_event_type')) == log4.keys()
    assert log4['_event_type'] == b'Logout'
    assert log4['_from'] == '0x' + utils.encode_hex(utils.privtoaddr(funded_privkey))

    # Need to vote 2 epochs before logout is active
    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    for i in range(0, casper.get_withdrawal_delay() + 1):
        new_epoch()

    cur_epoch = casper.get_current_epoch()
    end_epoch = casper.get_dynasty_start_epoch(casper.get_validators__end_dynasty(validator_index) + 1)
    assert cur_epoch == end_epoch + casper.get_withdrawal_delay()  # so we are allowed to withdraw

    casper.withdraw(validator_index)

    # Withdrawal log, finally
    log5 = get_last_log(casper_chain, casper)
    assert set(('_to', '_validator_index', '_amount', '_event_type')) == log5.keys()
    assert log5['_event_type'] == b'Withdraw'
    assert log5['_to'] == '0x' + utils.encode_hex(utils.privtoaddr(funded_privkey))
