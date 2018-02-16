def test_deposits(casper, funded_privkeys, deposit_amount, new_epoch, induct_validators):
    induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    assert casper.get_total_curdyn_deposits() == deposit_amount * len(funded_privkeys)
    assert casper.get_total_prevdyn_deposits() == 0


def test_deposits_on_staggered_dynasties(casper, funded_privkeys, deposit_amount, new_epoch,
                                         induct_validator, deposit_validator, mk_suggested_vote):
    initial_validator = induct_validator(funded_privkeys[0], deposit_amount)

    # finalize some epochs with just the one validator
    for i in range(3):
        casper.vote(mk_suggested_vote(initial_validator, funded_privkeys[0]))
        new_epoch()

    # induct more validators
    for privkey in funded_privkeys[1:]:
        deposit_validator(privkey, deposit_amount)

    assert casper.get_deposit_size(initial_validator) == casper.get_total_curdyn_deposits()

    casper.vote(mk_suggested_vote(initial_validator, funded_privkeys[0]))
    new_epoch()
    assert casper.get_deposit_size(initial_validator) == casper.get_total_curdyn_deposits()

    casper.vote(mk_suggested_vote(initial_validator, funded_privkeys[0]))
    new_epoch()
    assert casper.get_deposit_size(initial_validator) == casper.get_total_prevdyn_deposits()

    assert casper.get_deposit_size(initial_validator) == casper.get_total_prevdyn_deposits()


def test_justification_and_finalization(casper, funded_privkeys, deposit_amount, new_epoch,
                                        induct_validators, mk_suggested_vote):
    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    assert casper.get_total_curdyn_deposits() == deposit_amount * len(funded_privkeys)

    prev_dynasty = casper.get_dynasty()
    for _ in range(10):
        for i, validator_index in enumerate(validator_indexes):
            casper.vote(mk_suggested_vote(validator_index, funded_privkeys[i]))
        assert casper.get_main_hash_justified()
        assert casper.get_votes__is_finalized(casper.get_recommended_source_epoch())
        new_epoch()
        assert casper.get_dynasty() == prev_dynasty + 1
        prev_dynasty += 1


def test_voters_make_more(casper, funded_privkeys, deposit_amount, new_epoch,
                          induct_validators, mk_suggested_vote):
    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    assert casper.get_total_curdyn_deposits() == deposit_amount * len(funded_privkeys)

    nonvoting_index = validator_indexes[0]
    voting_indexes = validator_indexes[1:]
    voting_privkeys = funded_privkeys[1:]

    prev_dynasty = casper.get_dynasty()
    for _ in range(10):
        for i, validator_index in enumerate(voting_indexes):
            casper.vote(mk_suggested_vote(validator_index, voting_privkeys[i]))
        assert casper.get_main_hash_justified()
        assert casper.get_votes__is_finalized(casper.get_recommended_source_epoch())
        new_epoch()
        assert casper.get_dynasty() == prev_dynasty + 1
        prev_dynasty += 1

    voting_deposits = list(map(casper.get_deposit_size, voting_indexes))
    nonvoting_deposit = casper.get_deposit_size(nonvoting_index)
    assert len(set(voting_deposits)) == 1
    assert voting_deposits[0] > nonvoting_deposit


def test_logout(casper, funded_privkeys, deposit_amount, new_epoch,
                induct_validators, mk_suggested_vote, logout_validator):
    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    num_validators = len(validator_indexes)
    assert casper.get_total_curdyn_deposits() == deposit_amount * len(funded_privkeys)

    for _ in range(3):
        for i, validator_index in enumerate(validator_indexes):
            casper.vote(mk_suggested_vote(validator_index, funded_privkeys[i]))
        new_epoch()

    logged_out_index = validator_indexes[0]
    logged_out_privkey = funded_privkeys[0]
    logged_in_indexes = validator_indexes[1:]
    logged_in_privkeys = funded_privkeys[1:]

    logout_validator(logged_out_index, logged_out_privkey)
    for i, validator_index in enumerate(validator_indexes):
        casper.vote(mk_suggested_vote(validator_index, funded_privkeys[i]))
    new_epoch()

    for i, validator_index in enumerate(validator_indexes):
        casper.vote(mk_suggested_vote(validator_index, funded_privkeys[i]))
    new_epoch()

    logged_in_deposit_size = sum(map(casper.get_deposit_size, logged_in_indexes))
    logging_out_deposit_size = casper.get_deposit_size(logged_out_index)
    total_deposit_size = logged_in_deposit_size + logging_out_deposit_size

    assert abs(logged_in_deposit_size - casper.get_total_curdyn_deposits()) < num_validators
    assert abs(total_deposit_size - casper.get_total_prevdyn_deposits()) < num_validators

    for i, validator_index in enumerate(logged_in_indexes):
        casper.vote(mk_suggested_vote(validator_index, logged_in_privkeys[i]))
    new_epoch()

    logged_in_deposit_size = sum(map(casper.get_deposit_size, logged_in_indexes))

    assert abs(logged_in_deposit_size - casper.get_total_curdyn_deposits()) < num_validators
    assert abs(logged_in_deposit_size - casper.get_total_prevdyn_deposits()) < num_validators


def test_partial_online(casper, funded_privkeys, deposit_amount, new_epoch,
                        induct_validators, mk_suggested_vote):
    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    assert casper.get_total_curdyn_deposits() == deposit_amount * len(funded_privkeys)

    half_index = int(len(validator_indexes) / 2)
    online_indexes = validator_indexes[0:half_index]
    online_privkeys = funded_privkeys[0:half_index]
    offline_indexes = validator_indexes[half_index:-1]

    total_online_deposits = sum(map(casper.get_deposit_size, online_indexes))
    prev_ovp = total_online_deposits / casper.get_total_curdyn_deposits()

    for i in range(100):
        for i, validator_index in enumerate(online_indexes):
            casper.vote(mk_suggested_vote(validator_index, online_privkeys[i]))

        total_online_deposits = sum(map(casper.get_deposit_size, online_indexes))
        ovp = total_online_deposits / casper.get_total_curdyn_deposits()

        # after two non-finalized epochs, offline voters should start losing more
        if i >= 2:
            assert ovp > prev_ovp

        if ovp >= 0.75:
            assert casper.get_main_hash_justified()
            assert casper.get_votes__is_finalized(casper.get_recommended_source_epoch())
            break

        new_epoch()
        prev_ovp = ovp

    online_validator_deposit_size = sum(map(casper.get_deposit_size, online_indexes))
    offline_validator_deposit_size = sum(map(casper.get_deposit_size, offline_indexes))
    assert online_validator_deposit_size > offline_validator_deposit_size
