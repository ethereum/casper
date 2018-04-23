from ethereum import utils
from ethereum.tools.tester import TransactionFailed
import pytest

def test_deposit_succeeds_with_pure_sig_validator(casper, funded_privkey,
                                             deposit_amount,
                                             deposit_validator):
    withdrawal_addr = utils.privtoaddr(funded_privkey)

    validator_index = deposit_validator(
        funded_privkey,
        deposit_amount,
        "pure"
    )


def test_deposit_fails_with_sstore_in_sig_validator(casper, funded_privkey,
                                             deposit_amount,
                                             deposit_validator):
    withdrawal_addr = utils.privtoaddr(funded_privkey)

    with pytest.raises(TransactionFailed):
        validator_index = deposit_validator(
            funded_privkey,
            deposit_amount,
            "sstore"
        )


def test_deposit_fails_with_sload_in_sig_validator(casper, funded_privkey,
                                             deposit_amount,
                                             deposit_validator):
    withdrawal_addr = utils.privtoaddr(funded_privkey)

    with pytest.raises(TransactionFailed):
        validator_index = deposit_validator(
            funded_privkey,
            deposit_amount,
            "sload"
        )
