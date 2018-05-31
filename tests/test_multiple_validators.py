

def test_deposits(concise_casper,
                  funded_accounts,
                  validation_keys,
                  deposit_amount,
                  new_epoch,
                  induct_validators):
    induct_validators(
        funded_accounts,
        validation_keys,
        [deposit_amount] * len(funded_accounts)
    )
    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount * len(funded_accounts)
    assert concise_casper.total_prevdyn_deposits_in_wei() == 0


def test_deposits_on_staggered_dynasties(casper,
                                         concise_casper,
                                         funded_accounts,
                                         validation_keys,
                                         deposit_amount,
                                         new_epoch,
                                         induct_validator,
                                         deposit_validator,
                                         send_vote,
                                         mk_suggested_vote):
    initial_validator = induct_validator(funded_accounts[0], validation_keys[0], deposit_amount)

    # finalize some epochs with just the one validator
    for i in range(3):
        send_vote(mk_suggested_vote(initial_validator, validation_keys[0]))
        new_epoch()

    # induct more validators
    for account, key in zip(funded_accounts[1:], validation_keys[1:]):
        deposit_validator(account, key, deposit_amount)

    assert concise_casper.deposit_size(initial_validator) == \
        concise_casper.total_curdyn_deposits_in_wei()

    send_vote(mk_suggested_vote(initial_validator, validation_keys[0]))
    new_epoch()
    assert concise_casper.deposit_size(initial_validator) == \
        concise_casper.total_curdyn_deposits_in_wei()

    send_vote(mk_suggested_vote(initial_validator, validation_keys[0]))
    new_epoch()
    assert concise_casper.deposit_size(initial_validator) == \
        concise_casper.total_prevdyn_deposits_in_wei()


def test_justification_and_finalization(casper,
                                        concise_casper,
                                        funded_accounts,
                                        validation_keys,
                                        deposit_amount,
                                        new_epoch,
                                        induct_validators,
                                        send_vote,
                                        mk_suggested_vote):
    validator_indexes = induct_validators(
        funded_accounts,
        validation_keys,
        [deposit_amount] * len(funded_accounts)
    )
    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount * len(funded_accounts)

    prev_dynasty = concise_casper.dynasty()
    for _ in range(10):
        for key, validator_index in zip(validation_keys, validator_indexes):
            send_vote(mk_suggested_vote(validator_index, key))
        assert concise_casper.main_hash_justified()
        assert concise_casper.checkpoints__is_finalized(concise_casper.recommended_source_epoch())
        new_epoch()
        assert concise_casper.dynasty() == prev_dynasty + 1
        prev_dynasty += 1


def test_voters_make_more(casper,
                          concise_casper,
                          funded_accounts,
                          validation_keys,
                          deposit_amount,
                          new_epoch,
                          induct_validators,
                          send_vote,
                          mk_suggested_vote):
    validator_indexes = induct_validators(
        funded_accounts,
        validation_keys,
        [deposit_amount] * len(funded_accounts)
    )
    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount * len(funded_accounts)

    nonvoting_index = validator_indexes[0]
    voting_indexes = validator_indexes[1:]
    voting_keys = validation_keys[1:]

    prev_dynasty = concise_casper.dynasty()
    for _ in range(10):
        for key, validator_index in zip(voting_keys, voting_indexes):
            send_vote(mk_suggested_vote(validator_index, key))
        assert concise_casper.main_hash_justified()
        assert concise_casper.checkpoints__is_finalized(concise_casper.recommended_source_epoch())
        new_epoch()
        assert concise_casper.dynasty() == prev_dynasty + 1
        prev_dynasty += 1

    voting_deposits = list(map(concise_casper.deposit_size, voting_indexes))
    nonvoting_deposit = concise_casper.deposit_size(nonvoting_index)
    assert len(set(voting_deposits)) == 1
    assert voting_deposits[0] > nonvoting_deposit


def test_partial_online(casper,
                        concise_casper,
                        funded_accounts,
                        validation_keys,
                        deposit_amount,
                        new_epoch,
                        induct_validators,
                        send_vote,
                        mk_suggested_vote):
    validator_indexes = induct_validators(
        funded_accounts,
        validation_keys,
        [deposit_amount] * len(funded_accounts)
    )
    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount * len(funded_accounts)

    half_index = int(len(validator_indexes) / 2)
    online_indexes = validator_indexes[0:half_index]
    online_keys = validation_keys[0:half_index]
    offline_indexes = validator_indexes[half_index:-1]

    total_online_deposits = sum(map(concise_casper.deposit_size, online_indexes))
    prev_ovp = total_online_deposits / concise_casper.total_curdyn_deposits_in_wei()

    for i in range(100):
        for key, validator_index in zip(online_keys, online_indexes):
            send_vote(mk_suggested_vote(validator_index, key))

        total_online_deposits = sum(map(concise_casper.deposit_size, online_indexes))
        ovp = total_online_deposits / concise_casper.total_curdyn_deposits_in_wei()

        # after two non-finalized epochs, offline voters should start losing more
        if i >= 2:
            assert ovp > prev_ovp

        if ovp >= 0.75:
            assert concise_casper.main_hash_justified()
            assert concise_casper.checkpoints__is_finalized(
                concise_casper.recommended_source_epoch()
            )
            break

        new_epoch()
        prev_ovp = ovp

    online_validator_deposit_size = sum(map(concise_casper.deposit_size, online_indexes))
    offline_validator_deposit_size = sum(map(concise_casper.deposit_size, offline_indexes))
    assert online_validator_deposit_size > offline_validator_deposit_size
