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
                             .format(pure_prefix, impure_prefix, valcode_type))
    return matrix


@pytest.mark.parametrize(
    "valcode_type,should_succeed",
    build_pass_fail_matrix()
)
def test_valcode_purity_checks(casper,
                               funded_account,
                               validation_key,
                               assert_tx_failed,
                               deposit_amount,
                               deposit_validator,
                               valcode_type,
                               should_succeed,
                               deploy_validation_contract):
    if should_succeed:
        deposit_validator(
            funded_account,
            validation_key,
            deposit_amount,
            valcode_type
        )
    else:
        '''
        Check to ensure the validation_addr can actually be deployed.

        This can help detect fails that are not due to the purity
        checker, instead are a result of a bug in the contract being
        tested.
        '''
        deploy_validation_contract(funded_account, valcode_type)
        assert_tx_failed(lambda: deposit_validator(
            funded_account,
            validation_key,
            deposit_amount,
            valcode_type
        ))
