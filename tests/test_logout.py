from utils.common_assertions import (
    assert_validator_empty,
)


def test_logout_sets_end_dynasty(concise_casper,
                                 funded_account,
                                 validation_key,
                                 deposit_amount,
                                 induct_validator,
                                 logout_validator_via_signed_msg):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)

    expected_end_dynasty = concise_casper.dynasty() + concise_casper.DYNASTY_LOGOUT_DELAY()
    end_dynasty = concise_casper.validators__end_dynasty(validator_index)
    assert end_dynasty == 1000000000000000000000000000000

    logout_validator_via_signed_msg(validator_index, validation_key)

    end_dynasty = concise_casper.validators__end_dynasty(validator_index)
    assert end_dynasty == expected_end_dynasty


def test_logout_sets_total_deposits_at_logout(concise_casper,
                                              funded_account,
                                              validation_key,
                                              deposit_amount,
                                              induct_validator,
                                              logout_validator_via_signed_msg):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)
    assert concise_casper.validators__total_deposits_at_logout(validator_index) == 0

    logout_validator_via_signed_msg(validator_index, validation_key)

    deposits_at_logout = concise_casper.validators__total_deposits_at_logout(validator_index)
    assert deposits_at_logout == deposit_amount


def test_logout_updates_dynasty_wei_delta(concise_casper,
                                          funded_account,
                                          validation_key,
                                          deposit_amount,
                                          induct_validator,
                                          logout_validator_via_signed_msg):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)
    scaled_deposit_size = concise_casper.validators__deposit(validator_index)

    expected_end_dynasty = concise_casper.dynasty() + concise_casper.DYNASTY_LOGOUT_DELAY()
    assert concise_casper.dynasty_wei_delta(expected_end_dynasty) == 0

    logout_validator_via_signed_msg(validator_index, validation_key)

    assert concise_casper.dynasty_wei_delta(expected_end_dynasty) == -scaled_deposit_size


def test_logout_from_withdrawal_address_without_signature(concise_casper,
                                                          funded_account,
                                                          validation_key,
                                                          deposit_amount,
                                                          induct_validator,
                                                          logout_validator_via_unsigned_msg):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)
    expected_end_dynasty = concise_casper.dynasty() + concise_casper.DYNASTY_LOGOUT_DELAY()

    logout_validator_via_unsigned_msg(validator_index, funded_account)

    assert concise_casper.validators__end_dynasty(validator_index) == expected_end_dynasty


def test_logout_from_withdrawal_address_with_signature(concise_casper,
                                                       funded_account,
                                                       validation_key,
                                                       deposit_amount,
                                                       induct_validator,
                                                       logout_validator_via_signed_msg,
                                                       assert_tx_failed):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)
    expected_end_dynasty = concise_casper.dynasty() + concise_casper.DYNASTY_LOGOUT_DELAY()

    logout_validator_via_signed_msg(
        validator_index,
        validation_key,
        funded_account
    )

    assert concise_casper.validators__end_dynasty(validator_index) == expected_end_dynasty


def test_logout_from_non_withdrawal_address_without_signature(casper,
                                                              funded_accounts,
                                                              validation_keys,
                                                              deposit_amount,
                                                              induct_validator,
                                                              logout_validator_via_unsigned_msg,
                                                              assert_tx_failed):
    validator_key = validation_keys[0]
    validator_addr = funded_accounts[0]
    non_validator_addr = funded_accounts[1]
    assert validator_addr != non_validator_addr

    validator_index = induct_validator(validator_addr, validator_key, deposit_amount)

    assert_tx_failed(
        lambda: logout_validator_via_unsigned_msg(validator_index, non_validator_addr)
    )


def test_logout_from_non_withdrawal_address_with_signature(concise_casper,
                                                           funded_accounts,
                                                           validation_keys,
                                                           deposit_amount,
                                                           induct_validator,
                                                           logout_validator_via_signed_msg,
                                                           assert_tx_failed):
    validator_key = validation_keys[0]
    validator_addr = funded_accounts[0]
    non_validator_addr = funded_accounts[1]
    assert validator_addr != non_validator_addr

    validator_index = induct_validator(validator_addr, validator_key, deposit_amount)
    expected_end_dynasty = concise_casper.dynasty() + concise_casper.DYNASTY_LOGOUT_DELAY()

    logout_validator_via_signed_msg(
        validator_index,
        validator_key,
        non_validator_addr
    )

    assert concise_casper.validators__end_dynasty(validator_index) == expected_end_dynasty


def test_logout_with_multiple_validators(w3,
                                         casper,
                                         concise_casper,
                                         funded_accounts,
                                         validation_keys,
                                         deposit_amount,
                                         new_epoch,
                                         induct_validators,
                                         send_vote,
                                         mk_suggested_vote,
                                         logout_validator_via_signed_msg):
    validator_indexes = induct_validators(
        funded_accounts,
        validation_keys,
        [deposit_amount] * len(funded_accounts)
    )
    num_validators = len(validator_indexes)
    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount * len(funded_accounts)

    # finalize 3 epochs to get to a stable state
    for _ in range(3):
        for key, validator_index in zip(validation_keys, validator_indexes):
            send_vote(mk_suggested_vote(validator_index, key))
        new_epoch()

    # 0th logs out
    logged_out_index = validator_indexes[0]
    logged_out_key = validation_keys[0]
    logged_out_addr = funded_accounts[0]
    # the rest remain
    logged_in_indexes = validator_indexes[1:]
    logged_in_keys = validation_keys[1:]

    logout_validator_via_signed_msg(logged_out_index, logged_out_key)

    # enter validator's end_dynasty (validator in prevdyn)
    dynasty_logout_delay = concise_casper.DYNASTY_LOGOUT_DELAY()
    for _ in range(dynasty_logout_delay):
        for key, validator_index in zip(validation_keys, validator_indexes):
            send_vote(mk_suggested_vote(validator_index, key))
        new_epoch()
    assert concise_casper.validators__end_dynasty(logged_out_index) == concise_casper.dynasty()

    logged_in_deposit_size = sum(map(concise_casper.deposit_size, logged_in_indexes))
    logging_out_deposit_size = concise_casper.deposit_size(logged_out_index)
    total_deposit_size = logged_in_deposit_size + logging_out_deposit_size

    curdyn_deposits = concise_casper.total_curdyn_deposits_in_wei()
    prevdyn_deposits = concise_casper.total_prevdyn_deposits_in_wei()
    assert abs(logged_in_deposit_size - curdyn_deposits) < num_validators
    assert abs(total_deposit_size - prevdyn_deposits) < num_validators

    # validator no longer in prev or cur dyn
    for key, validator_index in zip(logged_in_keys, logged_in_indexes):
        send_vote(mk_suggested_vote(validator_index, key))
    new_epoch()

    logged_in_deposit_size = sum(map(concise_casper.deposit_size, logged_in_indexes))

    curdyn_deposits = concise_casper.total_curdyn_deposits_in_wei()
    prevdyn_deposits = concise_casper.total_prevdyn_deposits_in_wei()
    assert abs(logged_in_deposit_size - curdyn_deposits) < num_validators
    assert abs(logged_in_deposit_size - prevdyn_deposits) < num_validators

    # validator can withdraw after delay
    for _ in range(concise_casper.WITHDRAWAL_DELAY()):
        for key, validator_index in zip(logged_in_keys, logged_in_indexes):
            send_vote(mk_suggested_vote(validator_index, key))
        new_epoch()

    current_epoch = concise_casper.current_epoch()
    end_dynasty = concise_casper.validators__end_dynasty(logged_out_index)
    assert concise_casper.dynasty() > end_dynasty
    end_epoch = concise_casper.dynasty_start_epoch(end_dynasty + 1)

    # Allowed to withdraw
    assert current_epoch == end_epoch + concise_casper.WITHDRAWAL_DELAY()
 
    withdrawal_amount = int(
        concise_casper.validators__deposit(logged_out_index) * \
        concise_casper.deposit_scale_factor(end_epoch)
    )
    assert withdrawal_amount > 0

    # ensure withdrawal went to the addr
    prev_balance = w3.eth.getBalance(logged_out_addr)
    casper.functions.withdraw(logged_out_index).transact()
    balance = w3.eth.getBalance(logged_out_addr)
    assert balance > prev_balance
    assert balance - prev_balance == withdrawal_amount

    assert_validator_empty(concise_casper, logged_out_index)
