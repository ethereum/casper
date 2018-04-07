def test_deposits(casper, funded_privkeys, deposit_amount, new_epoch, induct_validators):
    induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    assert casper.total_curdyn_deposits_scaled() == deposit_amount * len(funded_privkeys)
    assert casper.total_prevdyn_deposits_scaled() == 0


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

    assert casper.deposit_size(initial_validator) == casper.total_curdyn_deposits_scaled()

    casper.vote(mk_suggested_vote(initial_validator, funded_privkeys[0]))
    new_epoch()
    assert casper.deposit_size(initial_validator) == casper.total_curdyn_deposits_scaled()

    casper.vote(mk_suggested_vote(initial_validator, funded_privkeys[0]))
    new_epoch()
    assert casper.deposit_size(initial_validator) == casper.total_prevdyn_deposits_scaled()


def test_justification_and_finalization(casper, funded_privkeys, deposit_amount, new_epoch,
                                        induct_validators, mk_suggested_vote):
    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    assert casper.total_curdyn_deposits_scaled() == deposit_amount * len(funded_privkeys)

    prev_dynasty = casper.dynasty()
    for _ in range(10):
        for i, validator_index in enumerate(validator_indexes):
            casper.vote(mk_suggested_vote(validator_index, funded_privkeys[i]))
        assert casper.main_hash_justified()
        assert casper.votes__is_finalized(casper.recommended_source_epoch())
        new_epoch()
        assert casper.dynasty() == prev_dynasty + 1
        prev_dynasty += 1


def test_voters_make_more(casper, funded_privkeys, deposit_amount, new_epoch,
                          induct_validators, mk_suggested_vote):
    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    assert casper.total_curdyn_deposits_scaled() == deposit_amount * len(funded_privkeys)

    nonvoting_index = validator_indexes[0]
    voting_indexes = validator_indexes[1:]
    voting_privkeys = funded_privkeys[1:]

    prev_dynasty = casper.dynasty()
    for _ in range(10):
        for i, validator_index in enumerate(voting_indexes):
            casper.vote(mk_suggested_vote(validator_index, voting_privkeys[i]))
        assert casper.main_hash_justified()
        assert casper.votes__is_finalized(casper.recommended_source_epoch())
        new_epoch()
        assert casper.dynasty() == prev_dynasty + 1
        prev_dynasty += 1

    voting_deposits = list(map(casper.deposit_size, voting_indexes))
    nonvoting_deposit = casper.deposit_size(nonvoting_index)
    assert len(set(voting_deposits)) == 1
    assert voting_deposits[0] > nonvoting_deposit


def test_partial_online(casper, funded_privkeys, deposit_amount, new_epoch,
                        induct_validators, mk_suggested_vote):
    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    assert casper.total_curdyn_deposits_scaled() == deposit_amount * len(funded_privkeys)

    half_index = int(len(validator_indexes) / 2)
    online_indexes = validator_indexes[0:half_index]
    online_privkeys = funded_privkeys[0:half_index]
    offline_indexes = validator_indexes[half_index:-1]

    total_online_deposits = sum(map(casper.deposit_size, online_indexes))
    prev_ovp = total_online_deposits / casper.total_curdyn_deposits_scaled()

    for i in range(100):
        for i, validator_index in enumerate(online_indexes):
            casper.vote(mk_suggested_vote(validator_index, online_privkeys[i]))

        total_online_deposits = sum(map(casper.deposit_size, online_indexes))
        ovp = total_online_deposits / casper.total_curdyn_deposits_scaled()

        # after two non-finalized epochs, offline voters should start losing more
        if i >= 2:
            assert ovp > prev_ovp

        if ovp >= 0.75:
            assert casper.main_hash_justified()
            assert casper.votes__is_finalized(casper.recommended_source_epoch())
            break

        new_epoch()
        prev_ovp = ovp

    online_validator_deposit_size = sum(map(casper.deposit_size, online_indexes))
    offline_validator_deposit_size = sum(map(casper.deposit_size, offline_indexes))
    assert online_validator_deposit_size > offline_validator_deposit_size
