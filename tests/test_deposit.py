from ethereum import utils


def test_deposit_sets_withdrawal_addr(casper, funded_privkey, deposit_amount,
                                      deposit_validator):
    withdrawal_addr = utils.privtoaddr(funded_privkey)
    validator_index = deposit_validator(funded_privkey, deposit_amount)

    withdrawal_addr_as_hex = '0x' + utils.encode_hex(withdrawal_addr)
    assert casper.validators__withdrawal_addr(validator_index) == withdrawal_addr_as_hex


def test_deposit_sets_validator_deposit(casper, funded_privkey, deposit_amount,
                                        deposit_validator):
    scale_factor = casper.deposit_scale_factor(casper.current_epoch())
    expected_scaled_deposit = deposit_amount / scale_factor
    validator_index = deposit_validator(funded_privkey, deposit_amount)

    assert casper.validators__deposit(validator_index) == expected_scaled_deposit


def test_deposit_updates_next_val_index(casper, funded_privkey, deposit_amount,
                                        deposit_validator):
    next_validator_index = casper.next_validator_index()
    validator_index = deposit_validator(funded_privkey, deposit_amount)
    assert validator_index == next_validator_index
    assert casper.next_validator_index() == next_validator_index + 1


def test_deposit_sets_start_dynasty(casper, funded_privkey, deposit_amount,
                                    deposit_validator):
    validator_index = deposit_validator(funded_privkey, deposit_amount)

    expected_start_dynasty = casper.dynasty() + 2
    assert casper.validators__start_dynasty(validator_index) == expected_start_dynasty


def test_deposit_sets_end_dynasty(casper, funded_privkey, deposit_amount,
                                  deposit_validator):
    validator_index = deposit_validator(funded_privkey, deposit_amount)

    expected_end_dynasty = 1000000000000000000000000000000
    assert casper.validators__end_dynasty(validator_index) == expected_end_dynasty


def test_deposit_updates_dynasty_wei_delta(casper, funded_privkey, deposit_amount,
                                           deposit_validator):
    start_dynasty = casper.dynasty() + 2
    assert casper.dynasty_wei_delta(start_dynasty) == 0

    validator_index = deposit_validator(funded_privkey, deposit_amount)
    scaled_deposit_size = casper.validators__deposit(validator_index)

    assert casper.dynasty_wei_delta(start_dynasty) == scaled_deposit_size


def test_deposit_updates_total_deposits(casper, funded_privkey, deposit_amount,
                                        induct_validator, mk_suggested_vote, new_epoch):
    assert casper.total_curdyn_deposits_scaled() == 0
    assert casper.total_prevdyn_deposits_scaled() == 0

    # note, full induction
    validator_index = induct_validator(funded_privkey, deposit_amount)

    assert casper.total_curdyn_deposits_scaled() == deposit_amount
    assert casper.total_prevdyn_deposits_scaled() == 0

    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()

    assert casper.total_curdyn_deposits_scaled() == deposit_amount
    assert casper.total_prevdyn_deposits_scaled() == deposit_amount


def test_deposit_increments_num_validators(casper, funded_privkey, deposit_amount,
                                           deposit_validator):
    prev_num_validators = casper.num_validators()
    assert prev_num_validators == 0

    deposit_validator(funded_privkey, deposit_amount)
    assert casper.num_validators() == prev_num_validators + 1


def test_deposit_increments_for_multiple_validators(casper, funded_privkeys,
                                                    deposit_amount, new_epoch,
                                                    induct_validators):
    assert casper.num_validators() == 0

    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))

    num_validators = len(validator_indexes)
    assert casper.num_validators() == num_validators


def test_deposit_minimum(casper, casper_config, funded_privkey,
                         deposit_amount, deposit_validator, assert_tx_failed):
    below_min_deposit = casper_config["min_deposit_size"] - 1
    assert_tx_failed(
        lambda: deposit_validator(funded_privkey, below_min_deposit)
    )

    below_min_deposit = 0
    assert_tx_failed(
        lambda: deposit_validator(funded_privkey, below_min_deposit)
    )

