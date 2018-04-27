from ethereum import utils
import pytest

from utils.valcodes import all_known_valcode_types


def build_pass_fail_matrix():
    matrix = []
    pure_prefix = "pure_"
    impure_prefix = "impure_"
    for valcode_type in all_known_valcode_types():
        if valcode_type.startswith(pure_prefix):
            matrix.append((valcode_type, True))
        elif valcode_type.startswith(impure_prefix):
            matrix.append((valcode_type, False))
        else:
            raise ValueError("Valcode keys should be prefixed with "
                             "{} (pass) or {} (fail) to indicate "
                             "as to if the test should pass or fail. "
                             "Given: {}."
                             .format(pure_prefix, impure_prefix,
                                    valcode_type))
    return matrix


@pytest.mark.parametrize(
    "valcode_type,should_succeed",
    build_pass_fail_matrix()
)
def test_valcode_purity_checks(casper, funded_privkey, assert_tx_failed,
                               deposit_amount, deposit_validator,
                               valcode_type, should_succeed,
                               validation_addr):
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
