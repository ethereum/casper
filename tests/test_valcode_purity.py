from ethereum import utils
import pytest


@pytest.mark.parametrize(
    "valcode_type,should_succeed",
    [
        ("pure", True),
        ("sstore", False),
        ("sload", False)
    ]
)
def test_valcode_purity_checks(casper, funded_privkey, assert_tx_failed,
                               deposit_amount, deposit_validator,
                               valcode_type, should_succeed):
    if should_succeed:
        validator_index = deposit_validator(
            funded_privkey,
            deposit_amount,
            valcode_type
        )
    else:
        assert_tx_failed(lambda: deposit_validator(
            funded_privkey,
            deposit_amount,
            valcode_type
        ))
