def test_partial_slash_no_dbl_prepare(casper, funded_privkey, deposit_amount, new_epoch,
                              induct_validator, mk_vote, fake_hash, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.get_total_curdyn_deposits() == deposit_amount

    vote_1 = mk_vote(
        validator_index,
        casper.get_recommended_target_hash(),
        casper.get_current_epoch(),
        casper.get_recommended_source_epoch(),
        funded_privkey
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        casper.get_current_epoch(),
        casper.get_recommended_source_epoch(),
        funded_privkey
    )
    old_deposit = casper.get_deposit_size(validator_index)
    casper.slash(vote_1, vote_2)
    assert casper.get_deposit_size(validator_index) == old_deposit * 0.835

def test_full_slash_no_dbl_prepare(casper, funded_privkey, deposit_amount, new_epoch,
                              induct_validator, mk_vote, fake_hash, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.get_total_curdyn_deposits() == deposit_amount

    vote_1 = mk_vote(
        validator_index,
        casper.get_recommended_target_hash(),
        casper.get_current_epoch(),
        casper.get_recommended_source_epoch(),
        funded_privkey
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        casper.get_current_epoch(),
        casper.get_recommended_source_epoch(),
        funded_privkey
    )

    initial_amount_deposited = casper.get_total_curdyn_deposits()
    initial_amount_destroyed = casper.get_total_destroyed()

    while (casper.get_total_destroyed()) < (int (initial_amount_deposited / 3)):
        casper.slash(vote_1, vote_2)

    # Check that in the same epoch the current deposit doesn't change
    assert  casper.get_total_curdyn_deposits() == initial_amount_deposited
    # Check that a total slash occured
    assert casper.get_deposit_size(validator_index) == 0

# Test to see if all the validators that acted malicious get slashed. 
# This doesn't work yet until v2 of slashing has been implemented. 
# def multiple_test_full_slash_no_dbl_prepare(casper, funded_privkey, deposit_amount, new_epoch,
#                               induct_validator, mk_vote, fake_hash, assert_tx_failed):

#     for i in range(len(funded_privkey)):
#         validator_index[i] = induct_validator(funded_privkey[i], deposit_amount)
#         assert casper.get_total_curdyn_deposits() == deposit_amount
#         vote_1[i] = mk_vote(
#             validator_index,
#             casper.get_recommended_target_hash(),
#             casper.get_current_epoch(),
#             casper.get_recommended_source_epoch(),
#             funded_privkey[i]
#         )
#         vote_2[i] = mk_vote(
#             validator_index,
#             fake_hash,
#             casper.get_current_epoch(),
#             casper.get_recommended_source_epoch(),
#             funded_privkey[i]
#         )

#         initial_amount_deposited = casper.get_total_curdyn_deposits()
#         initial_amount_destroyed = casper.get_total_destroyed()

#     for i in range(len(funded_privkey)):
#         casper.slash(vote_1[i], vote_2[i])

#     while (casper.get_total_destroyed()) < (int (initial_amount_deposited / 3)):
#         casper.slash(vote_1[0], vote_2[0])

#     # Check that in the same epoch the cur deposit doesn't change
#     assert  casper.get_total_curdyn_deposits() == initial_amount_deposited
#     # Check that a total slash occured
#     for i in range(len(funded_privkey)):
#         assert casper.get_deposit_size(validator_index) == 0


def test_slash_no_surround(casper, funded_privkey, deposit_amount, new_epoch,
                           induct_validator, mk_vote, fake_hash, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.get_total_curdyn_deposits() == deposit_amount

    vote_1 = mk_vote(
        validator_index,
        casper.get_recommended_target_hash(),
        casper.get_current_epoch(),
        casper.get_recommended_source_epoch() - 1,
        funded_privkey
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        casper.get_current_epoch() - 1,
        casper.get_recommended_source_epoch(),
        funded_privkey
    )

    old_deposit = casper.get_deposit_size(validator_index)
    casper.slash(vote_1, vote_2)
    assert casper.get_deposit_size(validator_index) == old_deposit * 0.835
