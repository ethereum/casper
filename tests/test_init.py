import pytest

from ethereum.tools.tester import TransactionFailed


def test_no_double_init(casper_args,
                        deploy_casper_contract,
                        assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    casper.init(*casper_args)
    assert_tx_failed(lambda: casper.init(*casper_args))


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
def test_start_epoch(test_chain, deploy_epoch, warm_up_period, expected_start_epoch,
                     epoch_length, casper_args, casper_config, deploy_casper_contract):
    test_chain.mine(
        epoch_length * deploy_epoch - test_chain.head_state.block_number
    )

    casper = deploy_casper_contract(casper_args, initialize_contract=False)
    casper.init(*casper_args)

    assert casper.START_EPOCH() == expected_start_epoch
    assert casper.current_epoch() == expected_start_epoch


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
def test_init_epoch_length(epoch_length, success, casper_args,
                           deploy_casper_contract, assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if not success:
        assert_tx_failed(lambda: casper.init(*casper_args))
        return

    casper.init(*casper_args)
    assert casper.EPOCH_LENGTH() == epoch_length


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
def test_init_warm_up_period(warm_up_period, success, casper_args,
                             deploy_casper_contract, assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if not success:
        assert_tx_failed(lambda: casper.init(*casper_args))
        return

    casper.init(*casper_args)
    assert casper.WARM_UP_PERIOD() == warm_up_period


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
def test_init_withdrawal_delay(withdrawal_delay, success, casper_args,
                               deploy_casper_contract, assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if not success:
        assert_tx_failed(lambda: casper.init(*casper_args))
        return

    casper.init(*casper_args)
    assert casper.WITHDRAWAL_DELAY() == withdrawal_delay


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
def test_init_dynasty_logout_delay(dynasty_logout_delay, success, casper_args,
                                   deploy_casper_contract, assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if not success:
        assert_tx_failed(lambda: casper.init(*casper_args))
        return

    casper.init(*casper_args)
    assert casper.DYNASTY_LOGOUT_DELAY() == dynasty_logout_delay


@pytest.mark.parametrize(
    'base_interest_factor, success',
    [
        (-10, False),
        (-0.001, False),
        (0, True),
        (7e-3, True),
        (0.1, True),
        (1.5, True),
    ]
)
def test_init_base_interest_factor(base_interest_factor, success, casper_args,
                                   deploy_casper_contract, assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if not success:
        assert_tx_failed(lambda: casper.init(*casper_args))
        return

    casper.init(*casper_args)
    assert casper.BASE_INTEREST_FACTOR() == base_interest_factor


@pytest.mark.parametrize(
    'base_penalty_factor, success',
    [
        (-10, False),
        (-0.001, False),
        (0, True),
        (7e-3, True),
        (0.1, True),
        (1.5, True),
    ]
)
def test_init_base_penalty_factor(base_penalty_factor, success, casper_args,
                                  deploy_casper_contract, assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if not success:
        assert_tx_failed(lambda: casper.init(*casper_args))
        return

    casper.init(*casper_args)
    assert casper.BASE_PENALTY_FACTOR() == base_penalty_factor


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
def test_init_min_deposit_size(min_deposit_size, success, casper_args,
                               deploy_casper_contract, assert_tx_failed):
    casper = deploy_casper_contract(casper_args, initialize_contract=False)

    if not success:
        assert_tx_failed(lambda: casper.init(*casper_args))
        return

    casper.init(*casper_args)
    assert casper.MIN_DEPOSIT_SIZE() == min_deposit_size
