import math

from web3 import Web3


def test_epoch_insta_finalize_logs(tester,
                                   concise_casper,
                                   casper_epoch_filter,
                                   new_epoch):
    start_epoch = concise_casper.START_EPOCH()
    new_epoch()
    new_epoch()
    logs = casper_epoch_filter.get_new_entries()
    assert len(logs) == 4
    log_old = logs[-2]['args']
    log_new = logs[-1]['args']

    log_fields = {
        '_number',
        '_checkpoint_hash',
        '_is_justified',
        '_is_finalized'
    }
    assert log_fields == log_old.keys()

    # New epoch log
    assert log_new['_number'] == start_epoch + 2
    init_block_number = tester.get_block_by_number('latest')['number'] - 1
    # block before epoch init == checkpoint hash
    assert Web3.toHex(log_new['_checkpoint_hash']) == \
        tester.get_block_by_number(init_block_number - 1)['hash']
    assert log_new['_is_justified'] is False
    assert log_new['_is_finalized'] is False

    # Insta-finalized previous epoch
    assert log_old['_number'] == start_epoch + 1
    # block before previous epoch init == checkpoint hash
    prev_epoch_block_number = init_block_number - concise_casper.EPOCH_LENGTH()
    assert Web3.toHex(log_old['_checkpoint_hash']) == \
        tester.get_block_by_number(prev_epoch_block_number - 1)['hash']
    assert log_old['_is_justified'] is True
    assert log_old['_is_finalized'] is True


def test_epoch_with_validator_logs(tester,
                                   casper,
                                   concise_casper,
                                   casper_epoch_filter,
                                   new_epoch,
                                   induct_validator,
                                   funded_account,
                                   validation_key,
                                   deposit_amount,
                                   send_vote,
                                   mk_suggested_vote):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)

    last_block_number = tester.get_block_by_number('latest')['number'] - 1

    send_vote(mk_suggested_vote(validator_index, validation_key))

    logs = casper_epoch_filter.get_new_entries()
    last_epoch_hash = tester.get_block_by_number(last_block_number - 1)['hash']
    last_epoch_log = [
        log for log in logs
        if Web3.toHex(log['args']['_checkpoint_hash']) == last_epoch_hash
    ][-1]['args']
    assert last_epoch_log['_is_justified'] is True
    assert last_epoch_log['_is_finalized'] is False

    new_epoch()
    last_block_number = tester.get_block_by_number('latest')['number'] - 1
    send_vote(mk_suggested_vote(validator_index, validation_key))

    logs = casper_epoch_filter.get_new_entries()
    last_epoch_hash = tester.get_block_by_number(last_block_number - 1)['hash']
    last_epoch_log = [
        log for log in logs
        if Web3.toHex(log['args']['_checkpoint_hash']) == last_epoch_hash
    ][-1]['args']
    prev_epoch_hash = tester.get_block_by_number(
        last_block_number - concise_casper.EPOCH_LENGTH() - 1
    )['hash']
    prev_epoch_log = [
        log for log in logs
        if Web3.toHex(log['args']['_checkpoint_hash']) == prev_epoch_hash
    ][-1]['args']

    assert prev_epoch_log['_is_justified'] is True
    assert prev_epoch_log['_is_finalized'] is True

    assert last_epoch_log['_is_justified'] is True
    assert last_epoch_log['_is_finalized'] is False


def test_deposit_log(concise_casper,
                     casper_deposit_filter,
                     funded_account,
                     validation_key,
                     new_epoch,
                     deposit_validator,
                     deposit_amount):
    start_epoch = concise_casper.START_EPOCH()
    new_epoch()
    assert concise_casper.current_epoch() == start_epoch + 1

    validator_index = deposit_validator(funded_account, validation_key, deposit_amount)

    logs = casper_deposit_filter.get_new_entries()
    assert len(logs) == 1
    log = logs[-1]['args']

    # Deposit log
    log_fields = {
        '_from',
        '_validation_address',
        '_validator_index',
        '_start_dyn',
        '_amount'
    }
    assert log_fields == log.keys()
    assert log['_from'] == funded_account
    assert log['_validation_address'] == concise_casper.validators__addr(validator_index)
    assert log['_validator_index'] == validator_index
    assert log['_start_dyn'] == concise_casper.validators__start_dynasty(validator_index)
    assert log['_amount'] == deposit_amount


def test_vote_log(casper,
                  concise_casper,
                  casper_vote_filter,
                  funded_account,
                  validation_key,
                  new_epoch,
                  induct_validator,
                  deposit_amount,
                  send_vote,
                  mk_suggested_vote):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)

    send_vote(mk_suggested_vote(validator_index, validation_key))

    logs = casper_vote_filter.get_new_entries()
    assert len(logs) == 1
    log = logs[-1]['args']

    log_fields = {
        '_from', '_validator_index',
        '_target_hash', '_target_epoch', '_source_epoch'
    }
    assert log_fields == log.keys()
    assert log['_from'] == funded_account
    assert log['_validator_index'] == validator_index
    assert log['_target_hash'] == concise_casper.recommended_target_hash()
    assert log['_target_epoch'] == concise_casper.recommended_source_epoch() + 1
    assert log['_source_epoch'] == concise_casper.recommended_source_epoch()


def test_logout_log(casper,
                    concise_casper,
                    casper_logout_filter,
                    funded_account,
                    validation_key,
                    new_epoch,
                    induct_validator,
                    deposit_amount,
                    send_vote,
                    mk_suggested_vote,
                    logout_validator_via_signed_msg):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)

    send_vote(mk_suggested_vote(validator_index, validation_key))

    logout_validator_via_signed_msg(validator_index, validation_key)

    logs = casper_logout_filter.get_new_entries()
    assert len(logs) == 1
    log = logs[-1]['args']

    log_fields = {
        '_from',
        '_validator_index',
        '_end_dyn'
    }
    assert log_fields == log.keys()
    assert log['_from'] == funded_account
    assert log['_validator_index'] == validator_index
    assert log['_end_dyn'] == concise_casper.dynasty() + concise_casper.DYNASTY_LOGOUT_DELAY()


def test_withdraw_log(w3,
                      casper,
                      concise_casper,
                      casper_withdraw_filter,
                      funded_account,
                      validation_key,
                      new_epoch,
                      induct_validator,
                      deposit_amount,
                      send_vote,
                      mk_suggested_vote,
                      logout_validator_via_signed_msg):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)

    send_vote(mk_suggested_vote(validator_index, validation_key))
    new_epoch()

    logout_validator_via_signed_msg(validator_index, validation_key)
    # Logout delay
    for _ in range(concise_casper.DYNASTY_LOGOUT_DELAY() + 1):
        send_vote(mk_suggested_vote(validator_index, validation_key))
        new_epoch()

    # In the next dynasty after end_dynasty
    assert concise_casper.validators__end_dynasty(validator_index) + 1 == concise_casper.dynasty()

    # Withdrawal delay
    for _ in range(concise_casper.WITHDRAWAL_DELAY()):
        new_epoch()

    current_epoch = concise_casper.current_epoch()
    end_dynasty = concise_casper.validators__end_dynasty(validator_index)
    end_epoch = concise_casper.dynasty_start_epoch(end_dynasty + 1)

    # Allowed to withdraw
    assert current_epoch == end_epoch + concise_casper.WITHDRAWAL_DELAY()

    expected_amount = concise_casper.deposit_size(validator_index)

    prev_balance = w3.eth.getBalance(funded_account)
    casper.functions.withdraw(validator_index).transact()
    balance = w3.eth.getBalance(funded_account)
    assert balance > prev_balance

    # Withdrawal log
    logs = casper_withdraw_filter.get_new_entries()
    assert len(logs) == 1
    log = logs[-1]['args']

    log_fields = {
        '_to',
        '_validator_index',
        '_amount'
    }
    assert log_fields == log.keys()
    assert log['_to'] == funded_account
    assert log['_validator_index'] == validator_index
    assert log['_amount'] == expected_amount


def test_slash_log(casper,
                   concise_casper,
                   casper_slash_filter,
                   funded_account,
                   validation_key,
                   new_epoch,
                   induct_validator,
                   deposit_amount,
                   mk_slash_votes,
                   base_sender,
                   logout_validator_via_signed_msg):
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)

    vote_1, vote_2 = mk_slash_votes(validator_index, validation_key)

    assert concise_casper.dynasty_wei_delta(concise_casper.dynasty() + 1) == 0

    # Save deposit before slashing
    validator_deposit = concise_casper.deposit_size(validator_index)
    casper.functions.slash(vote_1, vote_2).transact({'from': base_sender})

    # Slashed!
    assert concise_casper.validators__is_slashed(validator_index)

    # Slash log
    logs = casper_slash_filter.get_new_entries()
    assert len(logs) == 1
    log = logs[-1]['args']

    log_fields = {
        '_from',
        '_offender',
        '_offender_index',
        '_bounty',
    }
    assert log_fields == log.keys()
    assert log['_from'] == base_sender
    assert log['_offender'] == funded_account
    assert log['_offender_index'] == validator_index
    assert log['_bounty'] == math.floor(validator_deposit / 25)
