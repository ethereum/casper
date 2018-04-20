

def test_vote_single_validator(casper, funded_privkey, deposit_amount,
                               new_epoch, induct_validator, mk_suggested_vote):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.total_curdyn_deposits_scaled() == deposit_amount

    prev_dynasty = casper.dynasty()
    for i in range(10):
        casper.vote(mk_suggested_vote(validator_index, funded_privkey))
        assert casper.main_hash_justified()
        assert casper.votes__is_finalized(casper.recommended_source_epoch())
        new_epoch()
        assert casper.dynasty() == prev_dynasty + 1
        prev_dynasty += 1


def test_vote_target_epoch_twice(casper, funded_privkey, deposit_amount, new_epoch,
                                 induct_validator, mk_suggested_vote, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.total_curdyn_deposits_scaled() == deposit_amount

    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    # second vote on same target epoch fails
    assert_tx_failed(lambda: casper.vote(mk_suggested_vote(validator_index, funded_privkey)))


def test_non_finalization_loss(casper, funded_privkey, deposit_amount, new_epoch,
                               induct_validator, mk_suggested_vote, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.total_curdyn_deposits_scaled() == deposit_amount

    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()

    ds_prev_non_finalized = casper.deposit_size(validator_index)
    for i in range(5):
        new_epoch()
        ds_cur_non_finalized = casper.deposit_size(validator_index)
        assert ds_cur_non_finalized < ds_prev_non_finalized
        ds_prev_non_finalized = ds_cur_non_finalized


def test_mismatched_epoch_and_hash(casper, funded_privkey, deposit_amount,
                                   induct_validator, mk_vote, new_epoch, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.total_curdyn_deposits_scaled() == deposit_amount

    # step forward one epoch to ensure that validator is allowed
    # to vote on (current_epoch - 1)
    new_epoch()

    target_hash = casper.recommended_target_hash()
    mismatched_target_epoch = casper.current_epoch() - 1
    source_epoch = casper.recommended_source_epoch()

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
    assert casper.total_curdyn_deposits_scaled() == deposit_amount

    # finalize an epoch as a base to the test
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()

    # step forward 5 epochs without finalization
    for i in range(5):
        new_epoch()

    assert not casper.main_hash_justified()
    assert not casper.votes__is_finalized(casper.recommended_source_epoch())

    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    assert casper.main_hash_justified()
    assert not casper.votes__is_finalized(casper.recommended_source_epoch())

    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    assert casper.main_hash_justified()
    assert casper.votes__is_finalized(casper.recommended_source_epoch())
