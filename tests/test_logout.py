

def test_logout_with_multiple_validators(casper, funded_privkeys,
                                         deposit_amount, new_epoch, induct_validators,
                                         mk_suggested_vote, logout_validator):
    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    num_validators = len(validator_indexes)
    assert casper.get_total_curdyn_deposits() == deposit_amount * len(funded_privkeys)

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

    print(casper.get_dynasty_logout_delay())
    # mine logout transaction
    for i, validator_index in enumerate(validator_indexes):
        casper.vote(mk_suggested_vote(validator_index, funded_privkeys[i]))
    new_epoch()

    # enter first logout delay dynasty
    for i, validator_index in enumerate(validator_indexes):
        casper.vote(mk_suggested_vote(validator_index, funded_privkeys[i]))
    new_epoch()

    logged_in_deposit_size = sum(map(casper.get_deposit_size, logged_in_indexes))
    logging_out_deposit_size = casper.get_deposit_size(logged_out_index)
    total_deposit_size = logged_in_deposit_size + logging_out_deposit_size

    assert abs(logged_in_deposit_size - casper.get_total_curdyn_deposits()) < num_validators
    assert abs(total_deposit_size - casper.get_total_prevdyn_deposits()) < num_validators

    dynasties_to_logout = casper.get_dynasty_logout_delay()
    # finalized the rest of the epochs required to logout
    for _ in range(dynasties_to_logout-1):
        for i, validator_index in enumerate(logged_in_indexes):
            casper.vote(mk_suggested_vote(validator_index, logged_in_privkeys[i]))
        new_epoch()

    logged_in_deposit_size = sum(map(casper.get_deposit_size, logged_in_indexes))

    assert abs(logged_in_deposit_size - casper.get_total_curdyn_deposits()) < num_validators
    assert abs(logged_in_deposit_size - casper.get_total_prevdyn_deposits()) < num_validators
