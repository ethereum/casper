from ethereum import utils


def test_slash_no_dbl_prepare(casper, funded_privkey, deposit_amount, get_last_log,
                              induct_validator, mk_vote, fake_hash, casper_chain):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.get_total_curdyn_deposits() == deposit_amount

    vote_1 = mk_vote(
        validator_index,
        casper.get_recommended_target_hash(),
        casper.get_current_epoch(),
        casper.get_recommended_source_epoch(),
        funded_privkey
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        casper.get_current_epoch(),
        casper.get_recommended_source_epoch(),
        funded_privkey
    )

    next_dynasty = casper.get_dynasty() + 1
    assert casper.get_dynasty_wei_delta(casper.get_dynasty() + 1) == 0

    casper.slash(vote_1, vote_2)

    assert casper.get_deposit_size(validator_index) == 0
    assert casper.get_dynasty_wei_delta(next_dynasty) == \
        (-deposit_amount / casper.get_deposit_scale_factor())

    # Slash log
    log = get_last_log(casper_chain, casper)
    assert set(('_from', '_offender', '_offender_index',
                '_bounty', '_destroyed', '_event_type')) == log.keys()
    assert log['_event_type'] == b'Slash'
    assert log['_offender'] == '0x' + utils.encode_hex(utils.privtoaddr(funded_privkey))


def test_slash_no_surround(casper, funded_privkey, deposit_amount, new_epoch,
                           induct_validator, mk_vote, fake_hash, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.get_total_curdyn_deposits() == deposit_amount

    vote_1 = mk_vote(
        validator_index,
        casper.get_recommended_target_hash(),
        casper.get_current_epoch(),
        casper.get_recommended_source_epoch() - 1,
        funded_privkey
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        casper.get_current_epoch() - 1,
        casper.get_recommended_source_epoch(),
        funded_privkey
    )

    next_dynasty = casper.get_dynasty() + 1
    assert casper.get_dynasty_wei_delta(casper.get_dynasty() + 1) == 0

    casper.slash(vote_1, vote_2)
    assert casper.get_deposit_size(validator_index) == 0
    assert casper.get_dynasty_wei_delta(next_dynasty) == \
        (-deposit_amount / casper.get_deposit_scale_factor())
