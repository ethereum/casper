import pytest

from decimal import Decimal


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
    'epoch_length, success',
    [
        (-1, False),
        (0, False),
        (10, True),
        (250, True),
        (256, False),
        (500, False),
    ]
)
def test_init_epoch_length(
        epoch_length,
        success,
        casper_args,
        deploy_casper_contract,
        assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if not success:
        assert_tx_failed(
            lambda: casper.functions.init(*casper_args).transact()
        )
        return

    casper.functions.init(*casper_args).transact()
    assert casper.functions.EPOCH_LENGTH().call() == epoch_length


@pytest.mark.parametrize(
    'warm_up_period, success',
    [
        (-1, False),
        (0, True),
        (10, True),
        (256, True),
        (50000, True),
    ]
)
def test_init_warm_up_period(
        warm_up_period,
        success,
        casper_args,
        deploy_casper_contract,
        assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if not success:
        assert_tx_failed(
            lambda: casper.functions.init(*casper_args).transact()
        )
        return

    casper.functions.init(*casper_args).transact()
    assert casper.functions.WARM_UP_PERIOD().call() == warm_up_period


@pytest.mark.parametrize(
    'withdrawal_delay, success',
    [
        (-42, False),
        (-1, False),
        (0, True),
        (1, True),
        (10, True),
        (10000, True),
        (500000000, True),
    ]
)
def test_init_withdrawal_delay(
        withdrawal_delay,
        success,
        casper_args,
        deploy_casper_contract,
        assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if not success:
        assert_tx_failed(
            lambda: casper.functions.init(*casper_args).transact()
        )
        return

    casper.functions.init(*casper_args).transact()
    assert casper.functions.WITHDRAWAL_DELAY().call() == withdrawal_delay


@pytest.mark.parametrize(
    'dynasty_logout_delay, success',
    [
        (-42, False),
        (-1, False),
        (0, False),
        (1, False),
        (2, True),
        (3, True),
        (100, True),
        (3000000, True),
    ]
)
def test_init_dynasty_logout_delay(
        dynasty_logout_delay,
        success,
        casper_args,
        deploy_casper_contract,
        assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if not success:
        assert_tx_failed(
            lambda: casper.functions.init(*casper_args).transact()
        )
        return

    casper.functions.init(*casper_args).transact()
    assert casper.functions.DYNASTY_LOGOUT_DELAY().call() == dynasty_logout_delay


@pytest.mark.parametrize(
    'base_interest_factor, success',
    [
        (-10, False),
        (Decimal('-0.001'), False),
        (0, True),
        (Decimal('7e-3'), True),
        (Decimal('0.1'), True),
        (Decimal('1.5'), True),
    ]
)
def test_init_base_interest_factor(
        base_interest_factor,
        success,
        casper_args,
        deploy_casper_contract,
        assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if not success:
        assert_tx_failed(
            lambda: casper.functions.init(*casper_args).transact()
        )
        return

    casper.functions.init(*casper_args).transact()
    assert casper.functions.BASE_INTEREST_FACTOR().call() == base_interest_factor


@pytest.mark.parametrize(
    'base_penalty_factor, success',
    [
        (-10, False),
        (Decimal('-0.001'), False),
        (0, True),
        (Decimal('7e-3'), True),
        (Decimal('0.1'), True),
        (Decimal('1.5'), True),
    ]
)
def test_init_base_penalty_factor(
        base_penalty_factor,
        success,
        casper_args,
        deploy_casper_contract,
        assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if not success:
        assert_tx_failed(
            lambda: casper.functions.init(*casper_args).transact()
        )
        return

    casper.functions.init(*casper_args).transact()
    assert casper.functions.BASE_PENALTY_FACTOR().call() == base_penalty_factor


@pytest.mark.parametrize(
    'min_deposit_size, success',
    [
        (int(-1e10), False),
        (-1, False),
        (0, False),
        (1, True),
        (42, True),
        (int(1e4), True),
        (int(2.5e20), True),
        (int(5e30), True),
    ]
)
def test_init_min_deposit_size(
        min_deposit_size,
        success,
        casper_args,
        deploy_casper_contract,
        assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if not success:
        assert_tx_failed(
            lambda: casper.functions.init(*casper_args).transact()
        )
        return

    casper.functions.init(*casper_args).transact()
    assert casper.functions.MIN_DEPOSIT_SIZE().call() == min_deposit_size


def test_init_null_sender(
        null_sender,
        casper_args,
        deploy_casper_contract):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    casper.functions.init(*casper_args).transact()
    assert casper.functions.NULL_SENDER().call() == null_sender
