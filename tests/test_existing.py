def test_contract_deployed(casper):
    assert casper.nextValidatorIndex() == 1
    assert casper.current_epoch() == 0
