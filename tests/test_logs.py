from ethereum import utils


def test_logs(casper, funded_privkey, new_epoch, get_logs, deposit_validator,
              mk_suggested_vote, get_last_log, casper_chain, logout_validator):
    new_epoch()
    assert casper.current_epoch() == 1
    assert casper.next_validator_index() == 1

    validator_index = casper.next_validator_index()
    deposit_validator(funded_privkey, 1900 * 10**18)
    # Deposit log
    log1 = get_last_log(casper_chain, casper)
    assert set(('_from', '_validation_address', '_validator_index', '_start_dyn',
                '_amount', '_event_type')) == log1.keys()
    assert log1['_event_type'] == b'Deposit'
    assert log1['_from'] == '0x' + utils.encode_hex(utils.privtoaddr(funded_privkey))
    assert log1['_validator_index'] == validator_index

    new_epoch()
    # Test epoch logs
    receipt = casper_chain.head_state.receipts[-1]
    logs = get_logs(receipt, casper)
    log_old = logs[-2]
    log_new = logs[-1]

    assert set(('_number', '_checkpoint_hash', '_is_justified',
                '_is_finalized', '_event_type')) == log_old.keys()
    # New epoch log
    assert log_new['_event_type'] == b'Epoch'
    assert log_new['_number'] == 2
    assert log_new['_is_justified'] is False
    assert log_new['_is_finalized'] is False
    # Insta finalized previous
    assert log_old['_event_type'] == b'Epoch'
    assert log_old['_number'] == 1
    assert log_old['_is_justified'] is True
    assert log_old['_is_finalized'] is True

    new_epoch()
    new_epoch()

    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    # vote log
    log2 = get_last_log(casper_chain, casper)
    assert set(('_from', '_validator_index', '_target_hash',
                '_target_epoch', '_source_epoch', '_event_type')) == log2.keys()
    assert log2['_event_type'] == b'Vote'
    assert log2['_from'] == '0x' + utils.encode_hex(utils.privtoaddr(funded_privkey))

    new_epoch()
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    log3 = get_last_log(casper_chain, casper)
    assert log3['_event_type'] == b'Vote'

    logout_validator(validator_index, funded_privkey)
    # Logout log
    log4 = get_last_log(casper_chain, casper)
    assert set(('_from', '_validator_index', '_end_dyn', '_event_type')) == log4.keys()
    assert log4['_event_type'] == b'Logout'
    assert log4['_from'] == '0x' + utils.encode_hex(utils.privtoaddr(funded_privkey))

    # Need to vote 'DYNASTY_LOGOUT_DELAY' epochs before logout is active
    for _ in range(casper.DYNASTY_LOGOUT_DELAY()):
        new_epoch()
        casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    for i in range(casper.WITHDRAWAL_DELAY() + 1):
        new_epoch()

    cur_epoch = casper.current_epoch()
    end_epoch = casper.dynasty_start_epoch(
        casper.validators__end_dynasty(validator_index) + 1
    )
    assert cur_epoch == end_epoch + casper.WITHDRAWAL_DELAY()  # so we are allowed to withdraw

    casper.withdraw(validator_index)

    # Withdrawal log, finally
    log5 = get_last_log(casper_chain, casper)
    assert set(('_to', '_validator_index', '_amount', '_event_type')) == log5.keys()
    assert log5['_event_type'] == b'Withdraw'
    assert log5['_to'] == '0x' + utils.encode_hex(utils.privtoaddr(funded_privkey))
