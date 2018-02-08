def test_slash_no_dbl_prepare(casper, funded_privkey, deposit_amount, new_epoch,
                              induct_validator, mk_vote, fake_hash, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.get_total_curdyn_deposits() == deposit_amount

    vote_1 = mk_vote(
        validator_index,
        casper.get_recommended_target_hash(),
        casper.current_epoch(),
        casper.get_recommended_source_epoch(),
        funded_privkey
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        casper.current_epoch(),
        casper.get_recommended_source_epoch(),
        funded_privkey
    )

    casper.slash(vote_1, vote_2)
    assert casper.get_deposit_size(validator_index) == 0


def test_slash_no_surround(casper, funded_privkey, deposit_amount, new_epoch,
                           induct_validator, mk_vote, fake_hash, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.get_total_curdyn_deposits() == deposit_amount

    vote_1 = mk_vote(
        validator_index,
        casper.get_recommended_target_hash(),
        casper.current_epoch(),
        casper.get_recommended_source_epoch() - 1,
        funded_privkey
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        casper.current_epoch() - 1,
        casper.get_recommended_source_epoch(),
        funded_privkey
    )

    casper.slash(vote_1, vote_2)
    assert casper.get_deposit_size(validator_index) == 0
