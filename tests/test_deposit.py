import pytest


def test_deposit_sets_withdrawal_addr(concise_casper,
                                      funded_account,
                                      validation_key,
                                      deposit_amount,
                                      deposit_validator):
    validator_index = deposit_validator(funded_account, validation_key, deposit_amount)

    assert concise_casper.validators__withdrawal_addr(validator_index) == funded_account


def test_deposit_sets_validator_deposit(concise_casper,
                                        funded_account,
                                        validation_key,
                                        deposit_amount,
                                        deposit_validator):
    current_epoch = concise_casper.current_epoch()
    scale_factor = concise_casper.deposit_scale_factor(current_epoch)
    expected_scaled_deposit = deposit_amount / scale_factor
    validator_index = deposit_validator(funded_account, validation_key, deposit_amount)

    assert concise_casper.validators__deposit(validator_index) == expected_scaled_deposit


def test_deposit_updates_next_val_index(concise_casper,
                                        funded_account,
                                        validation_key,
                                        deposit_amount,
                                        deposit_validator):
    next_validator_index = concise_casper.next_validator_index()
    validator_index = deposit_validator(funded_account, validation_key, deposit_amount)
    assert validator_index == next_validator_index
    assert concise_casper.next_validator_index() == next_validator_index + 1


def test_deposit_sets_start_dynasty(concise_casper,
                                    funded_account,
                                    validation_key,
                                    deposit_amount,
                                    deposit_validator):
    validator_index = deposit_validator(funded_account, validation_key, deposit_amount)
    expected_start_dynasty = concise_casper.dynasty() + 2
    assert concise_casper.validators__start_dynasty(validator_index) == expected_start_dynasty


def test_deposit_sets_end_dynasty(concise_casper,
                                  funded_account,
                                  validation_key,
                                  deposit_amount,
                                  deposit_validator):
    validator_index = deposit_validator(funded_account, validation_key, deposit_amount)

    expected_end_dynasty = 1000000000000000000000000000000
    assert concise_casper.validators__end_dynasty(validator_index) == expected_end_dynasty


def test_deposit_is_not_slashed(concise_casper,
                                funded_account,
                                validation_key,
                                deposit_amount,
                                deposit_validator):
    validator_index = deposit_validator(funded_account, validation_key, deposit_amount)
    assert not concise_casper.validators__is_slashed(validator_index)


def test_deposit_total_deposits_at_logout(concise_casper,
                                          funded_account,
                                          validation_key,
                                          deposit_amount,
                                          deposit_validator):
    validator_index = deposit_validator(funded_account, validation_key, deposit_amount)

    assert concise_casper.validators__total_deposits_at_logout(validator_index) == 0


def test_deposit_updates_dynasty_wei_delta(concise_casper,
                                           funded_account,
                                           validation_key,
                                           deposit_amount,
                                           deposit_validator):
    start_dynasty = concise_casper.dynasty() + 2
    assert concise_casper.dynasty_wei_delta(start_dynasty) == 0

    validator_index = deposit_validator(funded_account, validation_key, deposit_amount)
    scaled_deposit_size = concise_casper.validators__deposit(validator_index)

    assert concise_casper.dynasty_wei_delta(start_dynasty) == scaled_deposit_size


def test_deposit_updates_total_deposits(casper,
                                        concise_casper,
                                        funded_account,
                                        validation_key,
                                        deposit_amount,
                                        induct_validator,
                                        mk_suggested_vote,
                                        send_vote,
                                        new_epoch):
    assert concise_casper.total_curdyn_deposits_in_wei() == 0
    assert concise_casper.total_prevdyn_deposits_in_wei() == 0

    # note, full induction
    validator_index = induct_validator(funded_account, validation_key, deposit_amount)

    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount
    assert concise_casper.total_prevdyn_deposits_in_wei() == 0

    send_vote(mk_suggested_vote(validator_index, validation_key))
    new_epoch()

    assert concise_casper.total_curdyn_deposits_in_wei() == deposit_amount
    assert concise_casper.total_prevdyn_deposits_in_wei() == deposit_amount


@pytest.mark.parametrize(
    'warm_up_period,epoch_length',
    [
        (10, 5),
        (25, 10),
        (100, 50),
    ]
)
def test_deposit_during_warm_up_period(concise_casper,
                                       funded_account,
                                       validation_key,
                                       deposit_amount,
                                       deposit_validator,
                                       new_epoch,
                                       warm_up_period,
                                       epoch_length):
    validator_index = deposit_validator(funded_account, validation_key, deposit_amount)

    expected_start_dynasty = concise_casper.dynasty() + 2
    assert concise_casper.validators__start_dynasty(validator_index) == expected_start_dynasty

    new_epoch()  # new_epoch mines through warm_up_period on first call
    concise_casper.dynasty() == 0
    new_epoch()
    concise_casper.dynasty() == 1
    new_epoch()
    concise_casper.dynasty() == 2

    concise_casper.total_curdyn_deposits_in_wei() == deposit_amount
    concise_casper.total_prevdyn_deposits_in_wei() == 0

    new_epoch()

    concise_casper.total_curdyn_deposits_in_wei() == deposit_amount
    concise_casper.total_prevdyn_deposits_in_wei() == deposit_amount
