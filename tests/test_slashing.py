from utils.common_assertions import (
    assert_validator_empty,
)
from utils.utils import encode_int32


def test_invalid_signature_fails(
        casper,
        concise_casper,
        funded_account,
        validation_key,
        deposit_amount,
        induct_validator,
        mk_vote,
        fake_hash,
        assert_tx_failed):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)

    # construct double votes but one has an invalid signature
    valid_signed_vote = mk_vote(
        validator_index,
        concise_casper.recommended_target_hash(),
        concise_casper.current_epoch(),
        concise_casper.recommended_source_epoch(),
        validation_key
    )
    invalid_signed_vote = mk_vote(
        validator_index,
        fake_hash,
        concise_casper.current_epoch(),
        concise_casper.recommended_source_epoch(),
        encode_int32(42)  # not the validators key
    )

    assert not concise_casper.slashable(valid_signed_vote, invalid_signed_vote)
    assert_tx_failed(
        lambda: casper.functions.slash(valid_signed_vote, invalid_signed_vote).transact()
    )

    # flip the order of arguments
    assert not concise_casper.slashable(invalid_signed_vote, valid_signed_vote)
    assert_tx_failed(
        lambda: casper.functions.slash(invalid_signed_vote, valid_signed_vote).transact()
    )


def test_different_validators_fails(
        casper,
        concise_casper,
        funded_accounts,
        validation_keys,
        deposit_amount,
        induct_validators,
        mk_vote,
        fake_hash,
        assert_tx_failed):
    validator_indexes = induct_validators(
        funded_accounts,
        validation_keys,
        [deposit_amount] * len(funded_accounts)
    )
    validator_index_1 = validator_indexes[0]
    key_1 = validation_keys[0]
    validator_index_2 = validator_indexes[1]
    key_2 = validation_keys[1]

    # construct conflicting vote from different validators
    valid_signed_vote = mk_vote(
        validator_index_1,
        concise_casper.recommended_target_hash(),
        concise_casper.current_epoch(),
        concise_casper.recommended_source_epoch(),
        key_1
    )
    invalid_signed_vote = mk_vote(
        validator_index_2,
        fake_hash,
        concise_casper.current_epoch(),
        concise_casper.recommended_source_epoch(),
        key_2  # not the validators key
    )

    assert not concise_casper.slashable(valid_signed_vote, invalid_signed_vote)
    assert_tx_failed(
        lambda: casper.functions.slash(valid_signed_vote, invalid_signed_vote).transact()
    )

    # flip the order of arguments
    assert not concise_casper.slashable(invalid_signed_vote, valid_signed_vote)
    assert_tx_failed(
        lambda: casper.functions.slash(invalid_signed_vote, valid_signed_vote).transact()
    )


def test_same_msg_fails(casper,
                        concise_casper,
                        funded_account,
                        validation_key,
                        deposit_amount,
                        induct_validator,
                        mk_vote,
                        assert_tx_failed):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)

    vote = mk_vote(
        validator_index,
        concise_casper.recommended_target_hash(),
        concise_casper.current_epoch(),
        concise_casper.recommended_source_epoch(),
        validation_key
    )

    assert not concise_casper.slashable(vote, vote)
    assert_tx_failed(lambda: casper.functions.slash(vote, vote).transact())


def test_double_slash_fails(casper,
                            concise_casper,
                            funded_account,
                            validation_key,
                            deposit_amount,
                            induct_validator,
                            mk_slash_votes,
                            assert_tx_failed):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)

    vote_1, vote_2 = mk_slash_votes(validator_index, validation_key)

    assert concise_casper.slashable(vote_1, vote_2)
    casper.functions.slash(vote_1, vote_2).transact()

    assert not concise_casper.slashable(vote_1, vote_2)
    assert_tx_failed(
        lambda: casper.functions.slash(vote_1, vote_2).transact()
    )


def test_slash_no_dbl_prepare(casper,
                              concise_casper,
                              funded_account,
                              validation_key,
                              deposit_amount,
                              induct_validator,
                              mk_vote,
                              fake_hash):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)
    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount

    vote_1 = mk_vote(
        validator_index,
        concise_casper.recommended_target_hash(),
        concise_casper.current_epoch(),
        concise_casper.recommended_source_epoch(),
        validation_key
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        concise_casper.current_epoch(),
        concise_casper.recommended_source_epoch(),
        validation_key
    )

    next_dynasty = concise_casper.dynasty() + 1
    assert concise_casper.dynasty_wei_delta(concise_casper.dynasty() + 1) == 0

    assert concise_casper.slashable(vote_1, vote_2)
    casper.functions.slash(vote_1, vote_2).transact()

    assert concise_casper.total_slashed(concise_casper.current_epoch()) == deposit_amount
    assert concise_casper.dynasty_wei_delta(next_dynasty) == \
        (-deposit_amount / concise_casper.deposit_scale_factor(concise_casper.current_epoch()))
    assert concise_casper.validators__is_slashed(validator_index)
    assert concise_casper.validators__end_dynasty(validator_index) == next_dynasty
    assert concise_casper.validators__total_deposits_at_logout(validator_index) == deposit_amount


def test_slash_no_surround(casper,
                           concise_casper,
                           funded_account,
                           validation_key,
                           deposit_amount,
                           new_epoch,
                           induct_validator,
                           mk_vote,
                           fake_hash,
                           assert_tx_failed):
    new_epoch()
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)
    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount

    vote_1 = mk_vote(
        validator_index,
        concise_casper.recommended_target_hash(),
        concise_casper.current_epoch(),
        concise_casper.recommended_source_epoch() - 1,
        validation_key
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        concise_casper.current_epoch() - 1,
        concise_casper.recommended_source_epoch(),
        validation_key
    )

    next_dynasty = concise_casper.dynasty() + 1
    assert concise_casper.dynasty_wei_delta(concise_casper.dynasty() + 1) == 0

    # ensure works both ways
    assert concise_casper.slashable(vote_1, vote_2)
    assert concise_casper.slashable(vote_2, vote_1)

    casper.functions.slash(vote_1, vote_2).transact()

    assert concise_casper.total_slashed(concise_casper.current_epoch()) == deposit_amount
    assert concise_casper.dynasty_wei_delta(next_dynasty) == \
        (-deposit_amount / concise_casper.deposit_scale_factor(concise_casper.current_epoch()))
    assert concise_casper.validators__is_slashed(validator_index)
    assert concise_casper.validators__end_dynasty(validator_index) == next_dynasty
    assert concise_casper.validators__total_deposits_at_logout(validator_index) == deposit_amount


def test_slash_after_logout_delay(casper,
                                  concise_casper,
                                  funded_account,
                                  validation_key,
                                  deposit_amount,
                                  induct_validator,
                                  send_vote,
                                  mk_suggested_vote,
                                  mk_slash_votes,
                                  new_epoch,
                                  fake_hash,
                                  logout_validator_via_signed_msg):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)
    scaled_deposit_size = concise_casper.validators__deposit(validator_index)

    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount

    logout_validator_via_signed_msg(validator_index, validation_key)
    end_dynasty = concise_casper.validators__end_dynasty(validator_index)
    assert concise_casper.validators__total_deposits_at_logout(validator_index) == deposit_amount

    assert concise_casper.dynasty_wei_delta(end_dynasty) == -scaled_deposit_size

    # step past validator's end_dynasty
    dynasty_logout_delay = concise_casper.DYNASTY_LOGOUT_DELAY()
    for _ in range(dynasty_logout_delay + 1):
        send_vote(mk_suggested_vote(validator_index, validation_key))
        new_epoch()

    new_deposit_size = concise_casper.deposit_size(validator_index)
    new_scaled_deposit_size = concise_casper.validators__deposit(validator_index)
    # should have a bit more from rewards
    assert new_scaled_deposit_size > scaled_deposit_size

    end_dynasty = concise_casper.validators__end_dynasty(validator_index)
    assert concise_casper.dynasty() == end_dynasty + 1
    assert concise_casper.dynasty_wei_delta(concise_casper.dynasty() + 1) == 0

    vote_1, vote_2 = mk_slash_votes(validator_index, validation_key)
    assert concise_casper.slashable(vote_1, vote_2)
    casper.functions.slash(vote_1, vote_2).transact()

    assert concise_casper.total_slashed(concise_casper.current_epoch()) == new_deposit_size
    assert concise_casper.validators__is_slashed(validator_index)
    assert concise_casper.validators__end_dynasty(validator_index) == end_dynasty
    # unchanged
    assert concise_casper.validators__total_deposits_at_logout(validator_index) == deposit_amount

    # validator already out of current deposits. should not change dynasty_wei_delta
    assert concise_casper.dynasty_wei_delta(end_dynasty) == -new_scaled_deposit_size
    assert concise_casper.dynasty_wei_delta(concise_casper.dynasty() + 1) == 0


def test_slash_after_logout_before_logout_delay(casper,
                                                concise_casper,
                                                funded_account,
                                                validation_key,
                                                deposit_amount,
                                                induct_validator,
                                                send_vote,
                                                mk_suggested_vote,
                                                mk_slash_votes,
                                                new_epoch,
                                                fake_hash,
                                                logout_validator_via_signed_msg):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)
    scaled_deposit_size = concise_casper.validators__deposit(validator_index)

    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount

    logout_validator_via_signed_msg(validator_index, validation_key)
    end_dynasty = concise_casper.validators__end_dynasty(validator_index)

    assert concise_casper.dynasty_wei_delta(end_dynasty) == -scaled_deposit_size

    # step forward but not up to end_dynasty
    send_vote(mk_suggested_vote(validator_index, validation_key))
    new_epoch()

    new_deposit_size = concise_casper.deposit_size(validator_index)
    new_scaled_deposit_size = concise_casper.validators__deposit(validator_index)

    assert concise_casper.dynasty() < end_dynasty - 1
    assert concise_casper.dynasty_wei_delta(concise_casper.dynasty() + 1) == 0
    assert concise_casper.dynasty_wei_delta(end_dynasty) == -new_scaled_deposit_size

    vote_1, vote_2 = mk_slash_votes(validator_index, validation_key)
    assert concise_casper.slashable(vote_1, vote_2)
    casper.functions.slash(vote_1, vote_2).transact()

    assert concise_casper.total_slashed(concise_casper.current_epoch()) == new_deposit_size
    assert concise_casper.validators__is_slashed(validator_index)
    assert concise_casper.validators__end_dynasty(validator_index) == concise_casper.dynasty() + 1

    # remove deposit from next dynasty rather than end_dynasty
    assert concise_casper.dynasty_wei_delta(end_dynasty) == 0
    assert concise_casper.dynasty_wei_delta(concise_casper.dynasty() + 1) == \
        -new_scaled_deposit_size
    # unchanged
    assert concise_casper.validators__total_deposits_at_logout(validator_index) == deposit_amount


def test_total_slashed(casper,
                       concise_casper,
                       funded_account,
                       validation_key,
                       deposit_amount,
                       new_epoch,
                       induct_validator,
                       send_vote,
                       mk_suggested_vote,
                       mk_slash_votes):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)

    vote_1, vote_2 = mk_slash_votes(validator_index, validation_key)
    casper.functions.slash(vote_1, vote_2).transact()

    current_epoch = concise_casper.current_epoch()
    assert concise_casper.total_slashed(current_epoch) == deposit_amount
    assert concise_casper.total_slashed(current_epoch + 1) == 0

    # step forwrd
    send_vote(mk_suggested_vote(validator_index, validation_key))
    new_epoch()

    current_epoch = concise_casper.current_epoch()
    assert concise_casper.total_slashed(current_epoch - 1) == deposit_amount
    assert concise_casper.total_slashed(current_epoch) == deposit_amount


def test_withdraw_after_slash(w3,
                              casper,
                              concise_casper,
                              funded_accounts,
                              validation_keys,
                              deposit_amount,
                              new_epoch,
                              induct_validators,
                              send_vote,
                              mk_suggested_vote,
                              mk_slash_votes):
    validator_indexes = induct_validators(
        funded_accounts,
        validation_keys,
        [deposit_amount] * len(funded_accounts)
    )
    slashed_fraction_of_total_deposits = 1.0 / len(funded_accounts)

    # 0th gets slashed
    slashed_index = validator_indexes[0]
    slashed_key = validation_keys[0]
    slashed_addr = funded_accounts[0]
    # the rest remain
    logged_in_indexes = validator_indexes[1:]
    logged_in_keys = validation_keys[1:]

    vote_1, vote_2 = mk_slash_votes(slashed_index, slashed_key)
    casper.functions.slash(vote_1, vote_2).transact()

    current_epoch = concise_casper.current_epoch()
    assert concise_casper.total_slashed(current_epoch) == deposit_amount
    assert concise_casper.total_slashed(current_epoch + 1) == 0

    # slashed validator can withdraw after end_dynasty plus delay
    for _ in range(concise_casper.WITHDRAWAL_DELAY() + 2):
        for i, validator_index in enumerate(logged_in_indexes):
            send_vote(mk_suggested_vote(validator_index, logged_in_keys[i]))
        new_epoch()

    end_dynasty = concise_casper.validators__end_dynasty(slashed_index)
    end_epoch = concise_casper.dynasty_start_epoch(end_dynasty + 1)
    withdrawal_epoch = end_epoch + concise_casper.WITHDRAWAL_DELAY()
    assert concise_casper.current_epoch() == withdrawal_epoch

    prev_balance = w3.eth.getBalance(slashed_addr)
    casper.functions.withdraw(slashed_index).transact()
    balance = w3.eth.getBalance(slashed_addr)
    assert concise_casper.current_epoch() == end_epoch + concise_casper.WITHDRAWAL_DELAY()

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

    assert_validator_empty(concise_casper, slashed_index)


def test_withdraw_after_majority_slash(w3,
                                       casper,
                                       concise_casper,
                                       funded_accounts,
                                       validation_keys,
                                       deposit_amount,
                                       new_epoch,
                                       induct_validators,
                                       send_vote,
                                       mk_suggested_vote,
                                       mk_slash_votes):
    validator_indexes = induct_validators(
        funded_accounts,
        validation_keys,
        [deposit_amount] * len(funded_accounts)
    )

    # 0th gets slashed
    slashed_indexes = validator_indexes[:-1]
    slashed_keys = validation_keys[:-1]
    slashed_addrs = funded_accounts[:-1]
    # the rest remain
    logged_in_index = validator_indexes[-1]
    logged_in_key = validation_keys[-1]

    assert len(slashed_indexes) / float(len(funded_accounts)) >= 1 / 3.0

    for slashed_index, slashed_key in zip(slashed_indexes, slashed_keys):
        vote_1, vote_2 = mk_slash_votes(slashed_index, slashed_key)
        casper.functions.slash(vote_1, vote_2).transact()

    current_epoch = concise_casper.current_epoch()
    assert concise_casper.total_slashed(current_epoch) == deposit_amount * len(slashed_indexes)
    assert concise_casper.total_slashed(current_epoch + 1) == 0

    # artificially simulate the slashed validators voting
    # normally if this occured, the validators would likely stop
    # voting and their deposits would have to bleed out.
    for i, validator_index in enumerate(validator_indexes):
        send_vote(mk_suggested_vote(validator_index, validation_keys[i]))
    new_epoch()

    # slashed validators can withdraw after end_dynasty plus delay
    for _ in range(concise_casper.WITHDRAWAL_DELAY() + 1):
        send_vote(mk_suggested_vote(logged_in_index, logged_in_key))
        new_epoch()

    assert concise_casper.dynasty() > concise_casper.validators__end_dynasty(slashed_indexes[0])

    prev_balances = [
        w3.eth.getBalance(slashed_addr)
        for slashed_addr in slashed_addrs
    ]
    for slashed_index in slashed_indexes:
        casper.functions.withdraw(slashed_index).transact()

    for slashed_addr, prev_balance in zip(slashed_addrs, prev_balances):
        balance = w3.eth.getBalance(slashed_addr)
        assert balance == prev_balance

    for slashed_index in slashed_indexes:
        assert_validator_empty(concise_casper, slashed_index)
