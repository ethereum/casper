def assert_validator_empty(casper, validator_index):
    assert casper.deposit_size(validator_index) == 0
    assert casper.validators__deposit(validator_index) == 0
    assert casper.validators__start_dynasty(validator_index) == 0
    assert casper.validators__end_dynasty(validator_index) == 0
    assert not casper.validators__is_slashed(validator_index)
    assert casper.validators__total_deposits_at_logout(validator_index) == 0
    assert not casper.validators__addr(validator_index)
    assert not casper.validators__withdrawal_addr(validator_index)
