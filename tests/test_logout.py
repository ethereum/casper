

def test_logout_sets_end_dynasty(casper, funded_privkey, deposit_amount,
                                 induct_validator, logout_validator):
    validator_index = induct_validator(funded_privkey, deposit_amount)

    expected_end_dynasty = casper.dynasty() + casper.DYNASTY_LOGOUT_DELAY()
    assert casper.validators__end_dynasty(validator_index) == 1000000000000000000000000000000

    logout_validator(validator_index, funded_privkey)

    assert casper.validators__end_dynasty(validator_index) == expected_end_dynasty


def test_logout_updates_dynasty_wei_delta(casper, funded_privkey, deposit_amount,
                                          induct_validator, logout_validator):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    scaled_deposit_size = casper.validators__deposit(validator_index)

    expected_end_dynasty = casper.dynasty() + casper.DYNASTY_LOGOUT_DELAY()
    assert casper.dynasty_wei_delta(expected_end_dynasty) == 0

    logout_validator(validator_index, funded_privkey)

    assert casper.dynasty_wei_delta(expected_end_dynasty) == -scaled_deposit_size


def test_logout_with_multiple_validators(casper, funded_privkeys,
                                         deposit_amount, new_epoch, induct_validators,
                                         mk_suggested_vote, logout_validator):
    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    num_validators = len(validator_indexes)
    assert casper.total_curdyn_deposits_scaled() == deposit_amount * len(funded_privkeys)

    # finalize 3 epochs to get to a stable state
    for _ in range(3):
        for i, validator_index in enumerate(validator_indexes):
            casper.vote(mk_suggested_vote(validator_index, funded_privkeys[i]))
        new_epoch()

    # 0th logs out
    logged_out_index = validator_indexes[0]
    logged_out_privkey = funded_privkeys[0]
    # the rest remain
    logged_in_indexes = validator_indexes[1:]
    logged_in_privkeys = funded_privkeys[1:]

    logout_validator(logged_out_index, logged_out_privkey)

    # enter validator's end_dynasty (validator in prevdyn)
    dynasty_logout_delay = casper.DYNASTY_LOGOUT_DELAY()
    for _ in range(dynasty_logout_delay):
        for i, validator_index in enumerate(validator_indexes):
            casper.vote(mk_suggested_vote(validator_index, funded_privkeys[i]))
        new_epoch()
    assert casper.validators__end_dynasty(logged_out_index) == casper.dynasty()

    logged_in_deposit_size = sum(map(casper.deposit_size, logged_in_indexes))
    logging_out_deposit_size = casper.deposit_size(logged_out_index)
    total_deposit_size = logged_in_deposit_size + logging_out_deposit_size

    assert abs(logged_in_deposit_size - casper.total_curdyn_deposits_scaled()) < num_validators
    assert abs(total_deposit_size - casper.total_prevdyn_deposits_scaled()) < num_validators

    # validator no longer in prev or cur dyn
    for i, validator_index in enumerate(logged_in_indexes):
        casper.vote(mk_suggested_vote(validator_index, logged_in_privkeys[i]))
    new_epoch()

    logged_in_deposit_size = sum(map(casper.deposit_size, logged_in_indexes))

    assert abs(logged_in_deposit_size - casper.total_curdyn_deposits_scaled()) < num_validators
    assert abs(logged_in_deposit_size - casper.total_prevdyn_deposits_scaled()) < num_validators

    # validator can withdraw after delay
    for i in range(casper.WITHDRAWAL_DELAY()):
        for i, validator_index in enumerate(logged_in_indexes):
            casper.vote(mk_suggested_vote(validator_index, logged_in_privkeys[i]))
        new_epoch()

    withdrawal_amount = casper.deposit_size(logged_out_index)
    assert withdrawal_amount > 0

    casper.withdraw(logged_out_index)
    assert casper.deposit_size(logged_out_index) == 0
    assert casper.validators__deposit(logged_out_index) == 0
    assert casper.validators__start_dynasty(logged_out_index) == 0
