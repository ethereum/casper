import math
from ethereum import utils


def test_epoch_insta_finalize_logs(casper, new_epoch, get_logs, casper_chain):
    new_epoch()
    new_epoch()
    # Test epoch logs
    receipt = casper_chain.head_state.receipts[-1]
    logs = get_logs(receipt, casper)
    assert len(logs) == 2
    log_old = logs[-2]
    log_new = logs[-1]

    assert {'_event_type', '_number', '_checkpoint_hash', '_is_justified', '_is_finalized'} == log_old.keys()

    # New epoch log
    assert log_new['_event_type'] == b'Epoch'
    assert log_new['_number'] == 2
    last_block_number = casper_chain.block.number
    # block before epoch init == checkpoint hash
    assert log_new['_checkpoint_hash'] == casper_chain.chain.get_blockhash_by_number(last_block_number - 1)
    assert log_new['_is_justified'] is False
    assert log_new['_is_finalized'] is False

    # Insta-finalized previous epoch
    assert log_old['_event_type'] == b'Epoch'
    assert log_old['_number'] == 1
    # block before previous epoch init == checkpoint hash
    prev_epoch_block_number = last_block_number - casper.EPOCH_LENGTH() - 1
    assert log_old['_checkpoint_hash'] == casper_chain.chain.get_blockhash_by_number(prev_epoch_block_number)
    assert log_old['_is_justified'] is True
    assert log_old['_is_finalized'] is True


def test_epoch_with_validator_logs(casper, new_epoch, get_logs, casper_chain,
                                   deposit_validator, funded_privkey, deposit_amount, mk_suggested_vote):
    validator_index = casper.next_validator_index()
    deposit_validator(funded_privkey, deposit_amount)
    # Validator is registered in Casper
    assert validator_index == casper.validator_indexes(utils.privtoaddr(funded_privkey))

    for _ in range(3):
        new_epoch()
    last_block_number = casper_chain.block.number
    # Allowed to vote now
    assert casper.validators__start_dynasty(validator_index) == casper.dynasty()

    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    receipt = casper_chain.head_state.receipts[-1]
    logs = get_logs(receipt, casper)
    assert len(logs) == 3 # Vote + Last Epoch + Prev Epoch
    last_epoch_hash = casper_chain.chain.get_blockhash_by_number(last_block_number - 1)
    last_epoch_log = [log for log in logs
                      if log['_event_type'] == b'Epoch' and log['_checkpoint_hash'] == last_epoch_hash][0]
    assert last_epoch_log['_is_justified'] is True
    assert last_epoch_log['_is_finalized'] is False

    new_epoch()
    last_block_number = casper_chain.block.number
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    receipt = casper_chain.head_state.receipts[-1]
    logs = get_logs(receipt, casper)
    assert len(logs) == 3 # Vote + Last Epoch + Prev Epoch
    last_epoch_hash = casper_chain.chain.get_blockhash_by_number(last_block_number - 1)
    last_epoch_log = [log for log in logs
                      if log['_event_type'] == b'Epoch' and log['_checkpoint_hash'] == last_epoch_hash][0]
    prev_epoch_hash = casper_chain.chain.get_blockhash_by_number(last_block_number - casper.EPOCH_LENGTH() - 1)
    prev_epoch_log = [log for log in logs
                      if log['_event_type'] == b'Epoch' and log['_checkpoint_hash'] == prev_epoch_hash][0]

    assert prev_epoch_log['_is_justified'] is True
    assert prev_epoch_log['_is_finalized'] is True

    assert last_epoch_log['_is_justified'] is True
    assert last_epoch_log['_is_finalized'] is False


def test_deposit_log(casper, funded_privkey, new_epoch, deposit_validator,
              deposit_amount, get_last_log, casper_chain):
    new_epoch()
    assert casper.current_epoch() == 1
    assert casper.next_validator_index() == 1

    validator_index = casper.next_validator_index()
    deposit_validator(funded_privkey, deposit_amount)
    # Validator is registered in Casper
    assert validator_index == casper.validator_indexes(utils.privtoaddr(funded_privkey))

    # Deposit log
    log = get_last_log(casper_chain, casper)
    assert {'_event_type', '_from', '_validation_address', '_validator_index', '_start_dyn', '_amount'} == log.keys()
    assert log['_event_type'] == b'Deposit'
    assert log['_from'] == '0x' + utils.encode_hex(utils.privtoaddr(funded_privkey))
    assert log['_validation_address'] == casper.validators__addr(validator_index)
    assert log['_validator_index'] == validator_index
    assert log['_start_dyn'] == casper.validators__start_dynasty(validator_index)
    assert log['_amount'] == deposit_amount


def test_vote_log(casper, funded_privkey, new_epoch, deposit_validator,
                     deposit_amount, get_last_log, casper_chain, mk_suggested_vote):
    new_epoch()
    validator_index = casper.next_validator_index()
    deposit_validator(funded_privkey, deposit_amount)
    # Validator is registered in Casper
    assert validator_index == casper.validator_indexes(utils.privtoaddr(funded_privkey))

    new_epoch()
    new_epoch()
    # Allowed to vote now
    assert casper.validators__start_dynasty(validator_index) == casper.dynasty()

    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    # Vote log
    log = get_last_log(casper_chain, casper)
    assert {'_event_type', '_from', '_validator_index', '_target_hash', '_target_epoch', '_source_epoch'} == log.keys()
    assert log['_event_type'] == b'Vote'
    assert log['_from'] == '0x' + utils.encode_hex(utils.privtoaddr(funded_privkey))
    assert log['_validator_index'] == validator_index
    assert log['_target_hash'] == casper.recommended_target_hash()
    assert log['_target_epoch'] == casper.recommended_source_epoch() + 1
    assert log['_source_epoch'] == casper.recommended_source_epoch()


def test_logout_log(casper, funded_privkey, new_epoch, deposit_validator, logout_validator,
                  deposit_amount, get_last_log, casper_chain, mk_suggested_vote):
    new_epoch()
    validator_index = casper.next_validator_index()
    deposit_validator(funded_privkey, deposit_amount)
    # Validator is registered in Casper
    assert validator_index == casper.validator_indexes(utils.privtoaddr(funded_privkey))

    new_epoch()
    new_epoch()
    # Allowed to vote now
    assert casper.validators__start_dynasty(validator_index) == casper.dynasty()

    casper.vote(mk_suggested_vote(validator_index, funded_privkey))

    logout_validator(validator_index, funded_privkey)
    # Logout log
    log = get_last_log(casper_chain, casper)
    assert {'_event_type', '_from', '_validator_index', '_end_dyn'} == log.keys()
    assert log['_event_type'] == b'Logout'
    assert log['_from'] == '0x' + utils.encode_hex(utils.privtoaddr(funded_privkey))
    assert log['_validator_index'] == validator_index
    assert log['_end_dyn'] == casper.dynasty() + casper.DYNASTY_LOGOUT_DELAY()


def test_withdraw_log(casper, funded_privkey, new_epoch, deposit_validator, logout_validator,
                    deposit_amount, get_last_log, casper_chain, mk_suggested_vote):
    new_epoch()
    validator_index = casper.next_validator_index()
    deposit_validator(funded_privkey, deposit_amount)
    # Validator is registered in Casper
    assert validator_index == casper.validator_indexes(utils.privtoaddr(funded_privkey))

    new_epoch()
    new_epoch()
    # Allowed to vote now
    assert casper.validators__start_dynasty(validator_index) == casper.dynasty()

    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()

    logout_validator(validator_index, funded_privkey)
    # Logout delay
    for _ in range(casper.DYNASTY_LOGOUT_DELAY() + 1):
        casper.vote(mk_suggested_vote(validator_index, funded_privkey))
        new_epoch()
    # In the next dynasty after end_dynasty
    assert casper.validators__end_dynasty(validator_index) + 1 == casper.dynasty()

    # Withdrawal delay
    for _ in range(casper.WITHDRAWAL_DELAY()):
        new_epoch()

    cur_epoch = casper.current_epoch()
    end_epoch = casper.dynasty_start_epoch(
        casper.validators__end_dynasty(validator_index) + 1
    )
    # Allowed to withdraw
    assert cur_epoch == end_epoch + casper.WITHDRAWAL_DELAY()

    expected_amount = casper.deposit_size(validator_index)
    casper.withdraw(validator_index)

    # Withdrawal log
    log = get_last_log(casper_chain, casper)
    assert {'_event_type', '_to', '_validator_index', '_amount'} == log.keys()
    assert log['_event_type'] == b'Withdraw'
    assert log['_to'] == '0x' + utils.encode_hex(utils.privtoaddr(funded_privkey))
    assert log['_validator_index'] == validator_index
    assert log['_amount'] == expected_amount


def test_slash_log(casper, funded_privkey, deposit_amount, get_last_log, base_sender_privkey,
                              induct_validator, mk_vote, fake_hash, casper_chain):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.total_curdyn_deposits_scaled() == deposit_amount

    vote_1 = mk_vote(
        validator_index,
        casper.recommended_target_hash(),
        casper.current_epoch(),
        casper.recommended_source_epoch(),
        funded_privkey
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        casper.current_epoch(),
        casper.recommended_source_epoch(),
        funded_privkey
    )

    assert casper.dynasty_wei_delta(casper.dynasty() + 1) == 0
    # Save deposit before slashing
    validator_deposit = casper.deposit_size(validator_index)

    casper.slash(vote_1, vote_2)
    # Slashed!
    assert casper.deposit_size(validator_index) == 0

    # Slash log
    log = get_last_log(casper_chain, casper)
    assert {'_event_type', '_from', '_offender', '_offender_index', '_bounty', '_destroyed'} == log.keys()
    assert log['_event_type'] == b'Slash'
    assert log['_from'] == '0x' + utils.encode_hex(utils.privtoaddr(base_sender_privkey))
    assert log['_offender'] == '0x' + utils.encode_hex(utils.privtoaddr(funded_privkey))
    assert log['_offender_index'] == validator_index
    assert log['_bounty'] == math.floor(validator_deposit / 25)
    assert log['_destroyed'] == validator_deposit - log['_bounty']
