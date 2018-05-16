from ethereum import utils

from utils.common_assertions import (
    assert_validator_empty,
)


def test_invalid_signature_fails(casper, funded_privkey, deposit_amount,
                                 induct_validator, mk_vote, fake_hash, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)

    # construct double votes but one has an invalid signature
    valid_signed_vote = mk_vote(
        validator_index,
        casper.recommended_target_hash(),
        casper.current_epoch(),
        casper.recommended_source_epoch(),
        funded_privkey
    )
    invalid_signed_vote = mk_vote(
        validator_index,
        fake_hash,
        casper.current_epoch(),
        casper.recommended_source_epoch(),
        b'\x42'  # not the validators key
    )

    assert not casper.slashable(valid_signed_vote, invalid_signed_vote)
    assert_tx_failed(lambda: casper.slash(valid_signed_vote, invalid_signed_vote))

    # flip the order of arguments
    assert not casper.slashable(invalid_signed_vote, valid_signed_vote)
    assert_tx_failed(lambda: casper.slash(invalid_signed_vote, valid_signed_vote))


def test_different_validators_fails(casper, funded_privkeys, deposit_amount,
                                    induct_validators, mk_vote, fake_hash, assert_tx_failed):
    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    validator_index_1 = validator_indexes[0]
    priv_key_1 = funded_privkeys[0]
    validator_index_2 = validator_indexes[1]
    priv_key_2 = funded_privkeys[1]

    # construct conflicting vote from different validators
    valid_signed_vote = mk_vote(
        validator_index_1,
        casper.recommended_target_hash(),
        casper.current_epoch(),
        casper.recommended_source_epoch(),
        priv_key_1
    )
    invalid_signed_vote = mk_vote(
        validator_index_2,
        fake_hash,
        casper.current_epoch(),
        casper.recommended_source_epoch(),
        priv_key_2  # not the validators key
    )

    assert not casper.slashable(valid_signed_vote, invalid_signed_vote)
    assert_tx_failed(lambda: casper.slash(valid_signed_vote, invalid_signed_vote))

    # flip the order of arguments
    assert not casper.slashable(invalid_signed_vote, valid_signed_vote)
    assert_tx_failed(lambda: casper.slash(invalid_signed_vote, valid_signed_vote))


def test_same_msg_fails(casper, funded_privkey, deposit_amount,
                        induct_validator, mk_vote, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)

    vote = mk_vote(
        validator_index,
        casper.recommended_target_hash(),
        casper.current_epoch(),
        casper.recommended_source_epoch(),
        funded_privkey
    )

    assert not casper.slashable(vote, vote)
    assert_tx_failed(lambda: casper.slash(vote, vote))


def test_double_slash_fails(casper, funded_privkey, deposit_amount,
                            induct_validator, mk_slash_votes, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)

    vote_1, vote_2 = mk_slash_votes(validator_index, funded_privkey)

    assert casper.slashable(vote_1, vote_2)
    casper.slash(vote_1, vote_2)

    assert not casper.slashable(vote_1, vote_2)
    assert_tx_failed(lambda: casper.slash(vote_1, vote_2))


def test_slash_no_dbl_prepare(casper, funded_privkey, deposit_amount,
                              induct_validator, mk_vote, fake_hash, casper_chain):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.total_curdyn_deposits_in_wei() == deposit_amount

    vote_1 = mk_vote(
        validator_index,
        casper.recommended_target_hash(),
        casper.current_epoch(),
        casper.recommended_source_epoch(),
        funded_privkey
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        casper.current_epoch(),
        casper.recommended_source_epoch(),
        funded_privkey
    )

    next_dynasty = casper.dynasty() + 1
    assert casper.dynasty_wei_delta(casper.dynasty() + 1) == 0

    assert casper.slashable(vote_1, vote_2)
    casper.slash(vote_1, vote_2)

    assert casper.total_slashed(casper.current_epoch()) == deposit_amount
    assert casper.dynasty_wei_delta(next_dynasty) == \
        (-deposit_amount / casper.deposit_scale_factor(casper.current_epoch()))
    assert casper.validators__is_slashed(validator_index)
    assert casper.validators__end_dynasty(validator_index) == next_dynasty
    assert casper.validators__total_deposits_at_logout(validator_index) == deposit_amount


def test_slash_no_surround(casper, funded_privkey, deposit_amount, new_epoch,
                           induct_validator, mk_vote, fake_hash, assert_tx_failed):
    new_epoch()
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.total_curdyn_deposits_in_wei() == deposit_amount

    vote_1 = mk_vote(
        validator_index,
        casper.recommended_target_hash(),
        casper.current_epoch(),
        casper.recommended_source_epoch() - 1,
        funded_privkey
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        casper.current_epoch() - 1,
        casper.recommended_source_epoch(),
        funded_privkey
    )

    next_dynasty = casper.dynasty() + 1
    assert casper.dynasty_wei_delta(casper.dynasty() + 1) == 0

    # ensure works both ways
    assert casper.slashable(vote_1, vote_2)
    assert casper.slashable(vote_2, vote_1)

    casper.slash(vote_1, vote_2)

    assert casper.total_slashed(casper.current_epoch()) == deposit_amount
    assert casper.dynasty_wei_delta(next_dynasty) == \
        (-deposit_amount / casper.deposit_scale_factor(casper.current_epoch()))
    assert casper.validators__is_slashed(validator_index)
    assert casper.validators__end_dynasty(validator_index) == next_dynasty
    assert casper.validators__total_deposits_at_logout(validator_index) == deposit_amount


def test_slash_after_logout_delay(casper, funded_privkey, deposit_amount,
                                  induct_validator, mk_suggested_vote, mk_slash_votes,
                                  new_epoch, fake_hash,
                                  logout_validator_via_signed_msg):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    scaled_deposit_size = casper.validators__deposit(validator_index)

    assert casper.total_curdyn_deposits_in_wei() == deposit_amount

    logout_validator_via_signed_msg(validator_index, funded_privkey)
    end_dynasty = casper.validators__end_dynasty(validator_index)
    assert casper.validators__total_deposits_at_logout(validator_index) == deposit_amount

    assert casper.dynasty_wei_delta(end_dynasty) == -scaled_deposit_size

    # step past validator's end_dynasty
    dynasty_logout_delay = casper.DYNASTY_LOGOUT_DELAY()
    for _ in range(dynasty_logout_delay + 1):
        casper.vote(mk_suggested_vote(validator_index, funded_privkey))
        new_epoch()

    new_deposit_size = casper.deposit_size(validator_index)
    new_scaled_deposit_size = casper.validators__deposit(validator_index)
    # should have a bit more from rewards
    assert new_scaled_deposit_size > scaled_deposit_size

    end_dynasty = casper.validators__end_dynasty(validator_index)
    assert casper.dynasty() == end_dynasty + 1
    assert casper.dynasty_wei_delta(casper.dynasty() + 1) == 0

    vote_1, vote_2 = mk_slash_votes(validator_index, funded_privkey)
    assert casper.slashable(vote_1, vote_2)
    casper.slash(vote_1, vote_2)

    assert casper.total_slashed(casper.current_epoch()) == new_deposit_size
    assert casper.validators__is_slashed(validator_index)
    assert casper.validators__end_dynasty(validator_index) == end_dynasty
    # unchanged
    assert casper.validators__total_deposits_at_logout(validator_index) == deposit_amount

    # validator already out of current deposits. should not change dynasty_wei_delta
    assert casper.dynasty_wei_delta(end_dynasty) == -new_scaled_deposit_size
    assert casper.dynasty_wei_delta(casper.dynasty() + 1) == 0


def test_slash_after_logout_before_logout_delay(casper, funded_privkey, deposit_amount,
                                                induct_validator,
                                                mk_suggested_vote, mk_slash_votes,
                                                new_epoch, fake_hash,
                                                logout_validator_via_signed_msg):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    scaled_deposit_size = casper.validators__deposit(validator_index)

    assert casper.total_curdyn_deposits_in_wei() == deposit_amount

    logout_validator_via_signed_msg(validator_index, funded_privkey)
    end_dynasty = casper.validators__end_dynasty(validator_index)

    assert casper.dynasty_wei_delta(end_dynasty) == -scaled_deposit_size

    # step forward but not up to end_dynasty
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()

    new_deposit_size = casper.deposit_size(validator_index)
    new_scaled_deposit_size = casper.validators__deposit(validator_index)

    assert casper.dynasty() < end_dynasty - 1
    assert casper.dynasty_wei_delta(casper.dynasty() + 1) == 0
    assert casper.dynasty_wei_delta(end_dynasty) == -new_scaled_deposit_size

    vote_1, vote_2 = mk_slash_votes(validator_index, funded_privkey)
    assert casper.slashable(vote_1, vote_2)
    casper.slash(vote_1, vote_2)

    assert casper.total_slashed(casper.current_epoch()) == new_deposit_size
    assert casper.validators__is_slashed(validator_index)
    assert casper.validators__end_dynasty(validator_index) == casper.dynasty() + 1

    # remove deposit from next dynasty rather than end_dynasty
    assert casper.dynasty_wei_delta(end_dynasty) == 0
    assert casper.dynasty_wei_delta(casper.dynasty() + 1) == -new_scaled_deposit_size
    # unchanged
    assert casper.validators__total_deposits_at_logout(validator_index) == deposit_amount


def test_total_slashed(casper, funded_privkey, deposit_amount, new_epoch,
                       induct_validator, mk_suggested_vote, mk_slash_votes):
    validator_index = induct_validator(funded_privkey, deposit_amount)

    vote_1, vote_2 = mk_slash_votes(validator_index, funded_privkey)
    casper.slash(vote_1, vote_2)

    current_epoch = casper.current_epoch()
    assert casper.total_slashed(current_epoch) == deposit_amount
    assert casper.total_slashed(current_epoch + 1) == 0

    # step forwrd
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()

    current_epoch = casper.current_epoch()
    assert casper.total_slashed(current_epoch - 1) == deposit_amount
    assert casper.total_slashed(current_epoch) == deposit_amount


def test_withdraw_after_slash(casper, casper_chain,
                              funded_privkeys, deposit_amount, new_epoch,
                              induct_validators, mk_suggested_vote, mk_slash_votes):
    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    slashed_fraction_of_total_deposits = 1.0 / len(funded_privkeys)

    # 0th gets slashed
    slashed_index = validator_indexes[0]
    slashed_privkey = funded_privkeys[0]
    slashed_public_key = utils.privtoaddr(slashed_privkey)
    # the rest remain
    logged_in_indexes = validator_indexes[1:]
    logged_in_privkeys = funded_privkeys[1:]

    vote_1, vote_2 = mk_slash_votes(slashed_index, slashed_privkey)
    casper.slash(vote_1, vote_2)

    current_epoch = casper.current_epoch()
    assert casper.total_slashed(current_epoch) == deposit_amount
    assert casper.total_slashed(current_epoch + 1) == 0

    # slashed validator can withdraw after end_dynasty plus delay
    for i in range(casper.WITHDRAWAL_DELAY() + 2):
        for i, validator_index in enumerate(logged_in_indexes):
            casper.vote(mk_suggested_vote(validator_index, logged_in_privkeys[i]))
        new_epoch()

    prev_balance = casper_chain.head_state.get_balance(slashed_public_key)
    casper.withdraw(slashed_index)
    balance = casper_chain.head_state.get_balance(slashed_public_key)
    assert balance > prev_balance

    expected_slashed_fraction = slashed_fraction_of_total_deposits * 3
    expected_withdrawal_fraction = 1 - expected_slashed_fraction
    expected_withdrawal_amount = expected_withdrawal_fraction * deposit_amount
    withdrawal_amount = balance - prev_balance
    assert withdrawal_amount < deposit_amount
    # should be less than because of some loss due to inactivity during withdrawal period
    assert withdrawal_amount < expected_withdrawal_amount
    # ensure within proximity to expected_withdrawal_amount
    assert withdrawal_amount > expected_withdrawal_amount * 0.9

    assert_validator_empty(casper, slashed_index)


def test_withdraw_after_majority_slash(casper, casper_chain,
                                       funded_privkeys, deposit_amount, new_epoch,
                                       induct_validators, mk_suggested_vote, mk_slash_votes):
    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))

    # 0th gets slashed
    slashed_indexes = validator_indexes[:-1]
    slashed_privkeys = funded_privkeys[:-1]
    slashed_public_keys = [
        utils.privtoaddr(slashed_privkey) for slashed_privkey in slashed_privkeys
    ]
    # the rest remain
    logged_in_index = validator_indexes[-1]
    logged_in_privkey = funded_privkeys[-1]

    assert len(slashed_indexes) / float(len(funded_privkeys)) >= 1 / 3.0

    for slashed_index, slashed_privkey in zip(slashed_indexes, slashed_privkeys):
        vote_1, vote_2 = mk_slash_votes(slashed_index, slashed_privkey)
        casper.slash(vote_1, vote_2)

    current_epoch = casper.current_epoch()
    assert casper.total_slashed(current_epoch) == deposit_amount * len(slashed_indexes)
    assert casper.total_slashed(current_epoch + 1) == 0

    # artificially simulate the slashed validators voting
    # normally if this occured, the validators would likely stop
    # voting and their deposits would have to bleed out.
    for i, validator_index in enumerate(validator_indexes):
        casper.vote(mk_suggested_vote(validator_index, funded_privkeys[i]))
    new_epoch()

    # slashed validators can withdraw after end_dynasty plus delay
    for i in range(casper.WITHDRAWAL_DELAY() + 1):
        casper.vote(mk_suggested_vote(logged_in_index, logged_in_privkey))
        new_epoch()

    assert casper.dynasty() > casper.validators__end_dynasty(slashed_indexes[0])

    prev_balances = [
        casper_chain.head_state.get_balance(slashed_public_key)
        for slashed_public_key in slashed_public_keys
    ]
    for slashed_index in slashed_indexes:
        casper.withdraw(slashed_index)

    for slashed_public_key, prev_balance in zip(slashed_public_keys, prev_balances):
        balance = casper_chain.head_state.get_balance(slashed_public_key)
        assert balance == prev_balance

    for slashed_index in slashed_indexes:
        assert_validator_empty(casper, slashed_index)
