import random


def test_deposits(casper, funded_privkeys, deposit_amount, new_epoch, induct_validators):
    induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    assert casper.get_total_curdyn_deposits() == deposit_amount * len(funded_privkeys)
    assert casper.get_total_prevdyn_deposits() == 0


def test_justification_and_finalization(casper, funded_privkeys, deposit_amount, new_epoch,
                                        induct_validators, mk_suggested_vote,
                                        assert_tx_failed):
    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    assert casper.get_total_curdyn_deposits() == deposit_amount * len(funded_privkeys)

    prev_dynasty = casper.dynasty()
    for i in range(10):
        drop_index = random.sample(validator_indexes, 1)
        for i, validator_index in enumerate(validator_indexes):
            # 1 validator each round doesn't vote
            # but we still have > 2/3 voting
            if validator_index == drop_index:
                continue
            casper.vote(mk_suggested_vote(validator_index, funded_privkeys[i]))
        assert casper.main_hash_justified()
        assert casper.votes__is_finalized(casper.get_recommended_source_epoch())
        new_epoch()
        assert casper.dynasty() == prev_dynasty + 1
        prev_dynasty += 1
