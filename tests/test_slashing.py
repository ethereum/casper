import pytest

from ethereum.tools import tester


@pytest.mark.parametrize(
    'privkey, amount',
    [
        (tester.k1, 2000 * 10**18),
        (tester.k1, 1000 * 10**18),
        (tester.k2, 1500 * 10**18),
    ]
)
def test_slash_no_dbl_prepare(casper, privkey, amount, new_epoch,
                              induct_validator, mk_vote, assert_tx_failed):
    # induct validator and step forward two dynasties
    validator_index = casper.nextValidatorIndex()
    induct_validator(privkey, amount)
    for i in range(3):
        new_epoch()
    assert casper.get_total_curdyn_deposits() == amount

    fake_hash = b'\xbc' * 32
    vote_1 = mk_vote(
        validator_index,
        casper.get_recommended_target_hash(),
        casper.current_epoch(),
        casper.get_recommended_source_epoch(),
        privkey
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        casper.current_epoch(),
        casper.get_recommended_source_epoch(),
        privkey
    )

    casper.slash(vote_1, vote_2)
    assert casper.get_deposit_size(validator_index) == 0


@pytest.mark.parametrize(
    'privkey, amount',
    [
        (tester.k1, 2000 * 10**18),
        (tester.k1, 1000 * 10**18),
        (tester.k2, 1500 * 10**18),
    ]
)
def test_slash_no_surround(casper, privkey, amount, new_epoch,
                           induct_validator, mk_vote, assert_tx_failed):
    # induct validator and step forward two dynasties
    validator_index = casper.nextValidatorIndex()
    induct_validator(privkey, amount)
    for i in range(3):
        new_epoch()
    assert casper.get_total_curdyn_deposits() == amount

    fake_hash = b'\xbc' * 32
    vote_1 = mk_vote(
        validator_index,
        casper.get_recommended_target_hash(),
        casper.current_epoch(),
        casper.get_recommended_source_epoch() - 1,
        privkey
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        casper.current_epoch() - 1,
        casper.get_recommended_source_epoch(),
        privkey
    )

    casper.slash(vote_1, vote_2)
    assert casper.get_deposit_size(validator_index) == 0


