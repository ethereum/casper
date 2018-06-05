import pytest

from decimal import Decimal
import web3
import eth_tester


TRANSACTION_FAILED = eth_tester.exceptions.TransactionFailed
VALIDATION_ERROR = web3.exceptions.ValidationError


def test_no_double_init(
        casper_args,
        deploy_casper_contract,
        assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    casper.functions.init(*casper_args).transact()
    assert_tx_failed(
        lambda: casper.functions.init(*casper_args).transact()
    )


@pytest.mark.parametrize(
    'deploy_epoch,warm_up_period,epoch_length,expected_start_epoch',
    [
        (0, 0, 50, 0),
        (0, 10, 50, 0),
        (0, 51, 50, 1),
        (0, 100, 50, 2),
        (1, 0, 20, 1),
        (1, 21, 20, 2),
        (4, 230, 50, 8),
        (10, 500, 25, 30)
    ]
)
def test_start_epoch(
        base_tester,
        deploy_epoch,
        warm_up_period,
        expected_start_epoch,
        epoch_length,
        casper_args,
        casper_config,
        deploy_casper_contract):
    block_number = base_tester.get_block_by_number('latest')['number']
    base_tester.mine_blocks(
        max(epoch_length * deploy_epoch - block_number - 1, 0)
    )

    casper = deploy_casper_contract(casper_args, initialize_contract=False)
    casper.functions.init(*casper_args).transact()

    assert casper.functions.START_EPOCH().call() == expected_start_epoch
    assert casper.functions.current_epoch().call() == expected_start_epoch


@pytest.mark.parametrize(
    'epoch_length, error',
    [
        (-1, VALIDATION_ERROR),
        (0, TRANSACTION_FAILED),
        (10, None),
        (250, None),
        (256, TRANSACTION_FAILED),
        (500, TRANSACTION_FAILED),
    ]
)
def test_init_epoch_length(
        epoch_length,
        error,
        casper_args,
        deploy_casper_contract,
        assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if error:
        assert_tx_failed(
            lambda: casper.functions.init(*casper_args).transact(),
            error
        )
        return

    casper.functions.init(*casper_args).transact()
    assert casper.functions.EPOCH_LENGTH().call() == epoch_length


@pytest.mark.parametrize(
    'warm_up_period, error',
    [
        (-1, VALIDATION_ERROR),
        (0, None),
        (10, None),
        (256, None),
        (50000, None),
    ]
)
def test_init_warm_up_period(warm_up_period,
                             error,
                             casper_args,
                             deploy_casper_contract,
                             assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if error:
        assert_tx_failed(
            lambda: casper.functions.init(*casper_args).transact(),
            error
        )
        return

    casper.functions.init(*casper_args).transact()
    assert casper.functions.WARM_UP_PERIOD().call() == warm_up_period

@pytest.mark.parametrize(
    'withdrawal_delay, error',
    [
        (-42, VALIDATION_ERROR),
        (-1, VALIDATION_ERROR),
        (0, None),
        (1, None),
        (10, None),
        (10000, None),
        (500000000, None),
    ]
)
def test_init_withdrawal_delay(withdrawal_delay,
                               error,
                               casper_args,
                               deploy_casper_contract,
                               assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if error:
        assert_tx_failed(
            lambda: casper.functions.init(*casper_args).transact(),
            error
        )
        return

    casper.functions.init(*casper_args).transact()
    assert casper.functions.WITHDRAWAL_DELAY().call() == withdrawal_delay


@pytest.mark.parametrize(
    'dynasty_logout_delay, error',
    [
        (-42, VALIDATION_ERROR),
        (-1, VALIDATION_ERROR),
        (0, TRANSACTION_FAILED),
        (1, TRANSACTION_FAILED),
        (2, None),
        (3, None),
        (100, None),
        (3000000, None),
    ]
)
def test_init_dynasty_logout_delay(dynasty_logout_delay,
                                   error,
                                   casper_args,
                                   deploy_casper_contract,
                                   assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if error:
        assert_tx_failed(
            lambda: casper.functions.init(*casper_args).transact(),
            error
        )
        return

    casper.functions.init(*casper_args).transact()
    assert casper.functions.DYNASTY_LOGOUT_DELAY().call() == dynasty_logout_delay


@pytest.mark.parametrize(
    'base_interest_factor, error',
    [
        (-10, TRANSACTION_FAILED),
        (Decimal('-0.001'), TRANSACTION_FAILED),
        (0, None),
        (Decimal('7e-3'), None),
        (Decimal('0.1'), None),
        (Decimal('1.5'), None),
    ]
)
def test_init_base_interest_factor(base_interest_factor,
                                   error,
                                   casper_args,
                                   deploy_casper_contract,
                                   assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if error:
        assert_tx_failed(
            lambda: casper.functions.init(*casper_args).transact(),
            error
        )
        return

    casper.functions.init(*casper_args).transact()
    assert casper.functions.BASE_INTEREST_FACTOR().call() == base_interest_factor


@pytest.mark.parametrize(
    'base_penalty_factor, error',
    [
        (-10, TRANSACTION_FAILED),
        (Decimal('-0.001'), TRANSACTION_FAILED),
        (0, None),
        (Decimal('7e-3'), None),
        (Decimal('0.1'), None),
        (Decimal('1.5'), None),
    ]
)
def test_init_base_penalty_factor(base_penalty_factor,
                                  error,
                                  casper_args,
                                  deploy_casper_contract,
                                  assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if error:
        assert_tx_failed(
            lambda: casper.functions.init(*casper_args).transact(),
            error
        )
        return

    casper.functions.init(*casper_args).transact()
    assert casper.functions.BASE_PENALTY_FACTOR().call() == base_penalty_factor


@pytest.mark.parametrize(
    'min_deposit_size, error',
    [
        (int(-1e10), VALIDATION_ERROR),
        (-1, VALIDATION_ERROR),
        (0, TRANSACTION_FAILED),
        (1, None),
        (42, None),
        (int(1e4), None),
        (int(2.5e20), None),
        (int(5e30), None),
    ]
)
def test_init_min_deposit_size(min_deposit_size,
                               error,
                               casper_args,
                               deploy_casper_contract,
                               assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if error:
        assert_tx_failed(
            lambda: casper.functions.init(*casper_args).transact(),
            error
        )
        return

    casper.functions.init(*casper_args).transact()
    assert casper.functions.MIN_DEPOSIT_SIZE().call() == min_deposit_size


def test_init_null_sender(null_sender,
                          casper_args,
                          deploy_casper_contract):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    casper.functions.init(*casper_args).transact()
    assert casper.functions.NULL_SENDER().call() == null_sender
