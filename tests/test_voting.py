import pytest


@pytest.mark.parametrize(
    'amount, min_deposit_size, success',
    [
        (2000 * 10**18, 2000 * 10**18, True),
        (1000 * 10**18, 100 * 10**18, True),
        (1500 * 10**18, 1499 * 10**18, True),
        (1, 1, True),

        # below min_deposit_size
        (999 * 10**18, 1000 * 10**18, False),
        (10 * 10**18, 1500 * 10**18, False),
        (0, 1, False),
    ]
)
def test_deposit(casper,
                 concise_casper,
                 funded_account,
                 validation_key,
                 amount,
                 success,
                 deposit_validator,
                 new_epoch,
                 assert_tx_failed):
    start_epoch = concise_casper.START_EPOCH()
    new_epoch()
    assert concise_casper.current_epoch() == start_epoch + 1
    assert concise_casper.next_validator_index() == 1

    if not success:
        assert_tx_failed(
            lambda: deposit_validator(funded_account, validation_key, amount)
        )
        return

    deposit_validator(funded_account, validation_key, amount)

    assert concise_casper.next_validator_index() == 2
    assert concise_casper.validator_indexes(funded_account) == 1
    assert concise_casper.deposit_size(1) == amount

    for i in range(2):
        new_epoch()

    assert concise_casper.dynasty() == 2
    assert concise_casper.total_curdyn_deposits_in_wei() == amount
    assert concise_casper.total_prevdyn_deposits_in_wei() == 0


def test_vote_single_validator(casper,
                               concise_casper,
                               funded_account,
                               validation_key,
                               deposit_amount,
                               new_epoch,
                               induct_validator,
                               mk_suggested_vote):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)
    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount

    prev_dynasty = concise_casper.dynasty()
    for i in range(10):
        vote_msg = mk_suggested_vote(validator_index, validation_key)
        assert concise_casper.votable(vote_msg)
        assert concise_casper.validate_vote_signature(vote_msg)
        casper.functions.vote(vote_msg).transact()
        assert concise_casper.main_hash_justified()
        assert concise_casper.checkpoints__is_finalized(concise_casper.recommended_source_epoch())
        new_epoch()
        assert concise_casper.dynasty() == prev_dynasty + 1
        prev_dynasty += 1


def test_vote_target_epoch_twice(casper,
                                 concise_casper,
                                 funded_account,
                                 validation_key,
                                 deposit_amount,
                                 new_epoch,
                                 induct_validator,
                                 mk_suggested_vote,
                                 assert_tx_failed):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)
    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount

    casper.functions.vote(
        mk_suggested_vote(validator_index, validation_key)
    ).transact()

    # second vote on same target epoch fails
    vote_msg = mk_suggested_vote(validator_index, validation_key)
    assert not concise_casper.votable(vote_msg)
    assert_tx_failed(
        lambda: casper.functions.vote(vote_msg).transact()
    )


@pytest.mark.parametrize(
    'valcode_type,success',
    [
        ('pure_greater_than_200k_gas', False),
        ('pure_between_100k-200k_gas', True),
    ]
)
def test_vote_validate_signature_gas_limit(valcode_type,
                                           success,
                                           casper,
                                           concise_casper,
                                           funded_account,
                                           validation_key,
                                           deposit_amount,
                                           induct_validator,
                                           mk_suggested_vote,
                                           assert_tx_failed):
    validator_index = induct_validator(
        funded_account,
        validation_key,
        deposit_amount,
        valcode_type
    )
    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount

    vote_msg = mk_suggested_vote(validator_index, validation_key)

    if not success:
        assert_tx_failed(
            lambda: concise_casper.validate_vote_signature(vote_msg)
        )
        assert_tx_failed(
            lambda: casper.functions.vote(vote_msg).transact()
        )
        return

    assert concise_casper.validate_vote_signature(vote_msg)
    casper.functions.vote(vote_msg).transact()


def test_non_finalization_loss(casper,
                               concise_casper,
                               funded_account,
                               validation_key,
                               deposit_amount,
                               new_epoch,
                               induct_validator,
                               mk_suggested_vote,
                               assert_tx_failed):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)
    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount

    casper.functions.vote(
        mk_suggested_vote(validator_index, validation_key)
    ).transact()
    new_epoch()

    casper.functions.vote(
        mk_suggested_vote(validator_index, validation_key)
    ).transact()
    new_epoch()

    ds_prev_non_finalized = concise_casper.deposit_size(validator_index)
    for i in range(5):
        new_epoch()
        ds_cur_non_finalized = concise_casper.deposit_size(validator_index)
        assert ds_cur_non_finalized < ds_prev_non_finalized
        ds_prev_non_finalized = ds_cur_non_finalized


def test_mismatched_epoch_and_hash(casper,
                                   concise_casper,
                                   funded_account,
                                   validation_key,
                                   deposit_amount,
                                   induct_validator,
                                   mk_vote,
                                   new_epoch,
                                   assert_tx_failed):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)
    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount

    # step forward one epoch to ensure that validator is allowed
    # to vote on (current_epoch - 1)
    new_epoch()

    target_hash = concise_casper.recommended_target_hash()
    mismatched_target_epoch = concise_casper.current_epoch() - 1
    source_epoch = concise_casper.recommended_source_epoch()

    mismatched_vote = mk_vote(
        validator_index,
        target_hash,
        mismatched_target_epoch,
        source_epoch,
        validation_key
    )

    assert not concise_casper.votable(mismatched_vote)
    assert_tx_failed(
        lambda: casper.functions.vote(mismatched_vote).transact()
    )


def test_consensus_after_non_finalization_streak(casper,
                                                 concise_casper,
                                                 funded_account,
                                                 validation_key,
                                                 deposit_amount,
                                                 new_epoch,
                                                 induct_validator,
                                                 mk_suggested_vote,
                                                 assert_tx_failed):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)
    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount

    # finalize an epoch as a base to the test
    casper.functions.vote(
        mk_suggested_vote(validator_index, validation_key)
    ).transact()
    new_epoch()

    casper.functions.vote(
        mk_suggested_vote(validator_index, validation_key)
    ).transact()
    new_epoch()

    # step forward 5 epochs without finalization
    for i in range(5):
        new_epoch()

    assert not concise_casper.main_hash_justified()
    assert not concise_casper.checkpoints__is_finalized(concise_casper.recommended_source_epoch())

    casper.functions.vote(
        mk_suggested_vote(validator_index, validation_key)
    ).transact()
    assert concise_casper.main_hash_justified()
    assert not concise_casper.checkpoints__is_finalized(concise_casper.recommended_source_epoch())

    new_epoch()
    casper.functions.vote(
        mk_suggested_vote(validator_index, validation_key)
    ).transact()

    assert concise_casper.main_hash_justified()
    assert concise_casper.checkpoints__is_finalized(concise_casper.recommended_source_epoch())
