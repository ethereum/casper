from ethereum.tools import tester as t
from ethereum import utils, common, transactions, abi
from casper_tester_helper_functions import mk_initializers, casper_config, new_epoch, custom_chain, \
    viper_rlp_decoder_address, sig_hasher_address, purity_checker_address, purity_checker_abi, \
    purity_checker_ct, mk_vote, deploy_test_rlp, induct_validator, mk_logout
from viper import compiler
from viper import utils as viper_utils
import serpent
from ethereum.slogging import LogRecorder, configure_logging, set_level
config_string = ':info,eth.vm.log:trace,eth.vm.op:trace,eth.vm.stack:trace,eth.vm.exit:trace,eth.pb.msg:trace,eth.pb.tx:debug'
#configure_logging(config_string=config_string)
import rlp
alloc = {}
alloc[t.a0] = {'balance': 100000 * utils.denoms.ether}
s = custom_chain(t, alloc, 9999999, 4707787, 2000000)

EPOCH_LENGTH = casper_config["epoch_length"]

# Install Casper, RLP decoder, purity checker, sighasher
casper_address, casper_abi = mk_initializers(casper_config, s, t.k0)

# Check that the RLP decoding library and the sig hashing library are "pure"
assert utils.big_endian_to_int(s.tx(t.k0, purity_checker_address, 0, purity_checker_ct.encode('submit', [viper_rlp_decoder_address]))) == 1
assert utils.big_endian_to_int(s.tx(t.k0, purity_checker_address, 0, purity_checker_ct.encode('submit', [sig_hasher_address]))) == 1
print("Sig hasher deployed at %s" % sig_hasher_address)


casper = t.ABIContract(s, casper_abi, casper_address)
s.mine(1)

print(viper_rlp_decoder_address)
print(viper_utils.RLP_DECODER_ADDRESS)
assert viper_utils.bytes_to_int(viper_rlp_decoder_address) == viper_utils.RLP_DECODER_ADDRESS

print("Casper Contract deployed at: %s" % (casper_address))

rlp_abi, rlp_addr = deploy_test_rlp(s, t.k0)
rlp_contract = t.ABIContract(s, rlp_abi, rlp_addr)
print("CHECK RLP SHOULD EQUAL 4: %s" % rlp_contract.fos())

# Helper functions for making a prepare, commit, login and logout message
# Begin the test

print("Starting tests")
# Initialize the first epoch
current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)
assert current_dyn == 0
assert casper.nextValidatorIndex() == 1
assert casper.current_epoch() == 1
print("Epoch initialized")

# Deposit one validator
VAL_1_DEPOSIT_SIZE = 2000 * 10**18
induct_validator(s, casper, t.k1, VAL_1_DEPOSIT_SIZE)
# Mine two epochs
current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)
current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)
assert current_dyn == 2
assert casper.get_total_curdyn_deposits() == VAL_1_DEPOSIT_SIZE
assert casper.get_total_prevdyn_deposits() == 0

print("target_hash: %s" % _th)
print("target_epoch: %s" % _te)
print("source_epoch: %s" % _se)
print("current_dyn: %s" % current_dyn)
print(_th)
print(casper.get_recommended_target_hash())
# Send a vote
print("attempting to vote...")
print('pre deposit', casper.get_deposit_size(1), casper.get_total_curdyn_deposits())
assert casper.get_deposit_size(1) == casper.get_total_curdyn_deposits()

# print(mk_vote(1, _th, _te, _se, t.k1))
# print(casper.test_vote(mk_vote(1, _th, _te, _se, t.k1)))

casper.vote(mk_vote(1, _th, _te, _se, t.k1))
print('Gas consumed for a vote: %d' % s.last_gas_used(with_tx=True))
print(casper.votes__cur_dyn_votes(_te, _se))
print(casper.votes__is_justified(_te))

assert casper.votes__cur_dyn_votes(_te, _se) == VAL_1_DEPOSIT_SIZE / casper.deposit_scale_factor(_te)
assert casper.votes__is_justified(_te)
assert casper.main_hash_justified()

print("Vote message processed")
print("Attempt second vote on same target epoch")
try:
    casper.vote(mk_vote(1, _th, _te, _se, t.k1))
    success = True
except:
    success = False
assert not success
print("Vote fails the second time")
# Send a commit message
print('post deposit', casper.get_deposit_size(1))
# Check that we committed

# Initialize the fourth epoch 
current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)
# Check that the dynasty increased as expected
assert current_dyn == 3
print(casper.get_total_prevdyn_deposits(), casper.get_total_curdyn_deposits())
print("Second epoch initialized, dynasty increased as expected")
# Send a vote message
print('pre deposit', casper.get_deposit_size(1), casper.get_total_curdyn_deposits())
assert casper.get_deposit_size(1) == casper.get_total_curdyn_deposits()

casper.vote(mk_vote(1, _th, _te, _se, t.k1))
assert casper.main_hash_justified()
print('post deposit', casper.get_deposit_size(1))
# Check that source epoch is finalized
assert casper.votes__is_finalized(_se)

# Initialize the fifth epoch
current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)
print('Last nonvoter rescale:\t%s' % casper.last_nonvoter_rescale())
print('Last voter rescale:\t%s' % casper.last_voter_rescale())
print('Epoch %s deposit scale factor:\t%s' % (_te, casper.deposit_scale_factor(_te)))
print('pre deposit', casper.get_deposit_size(1))
assert casper.get_deposit_size(1) == casper.get_total_curdyn_deposits()

# Test the NO_DBL_PREPARE slashing condition
fake_hash = b'\xbc' * 32
vote_1 = mk_vote(1, _th, _te, _se, t.k1)
vote_2 = mk_vote(1, fake_hash, _te, _se, t.k1)
snapshot = s.snapshot()
casper.slash(vote_1, vote_2)
assert casper.get_deposit_size(1) == 0
s.revert(snapshot)
print("NO_DBL_VOTE slashing condition works")

# Test the NO_SURROUND_VOTE slashing condition
vote_1 = mk_vote(1, _th, _te, _se - 1, t.k1)
vote_2 = mk_vote(1, fake_hash, _te - 1, _se, t.k1)
snapshot = s.snapshot()
casper.slash(vote_1, vote_2)
s.revert(snapshot)
print("NO_SURROUND_VOTE slashing condition works")

# Finish the fifth epoch
casper.vote(mk_vote(1, _th, _te, _se, t.k1))
assert casper.main_hash_justified()
print('post deposit', casper.get_deposit_size(1))
# Check that source epoch is finalized
assert casper.votes__is_finalized(_se)

# Test non-finalization losses
ds_0_non_finalized = casper.get_deposit_size(1)
current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)
ds_1_non_finalized = casper.get_deposit_size(1)
print("Non-finalization losses (first epoch): %.4f" % (1 - ds_1_non_finalized / ds_0_non_finalized))
assert ds_1_non_finalized < ds_0_non_finalized
current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)
ds_2_non_finalized = casper.get_deposit_size(1)
print("Non-finalization losses (second epoch): %.4f" % (1 - ds_2_non_finalized / ds_1_non_finalized))
current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)
ds_3_non_finalized = casper.get_deposit_size(1)
print("Non-finalization losses (third epoch): %.4f" % (1 - ds_3_non_finalized / ds_2_non_finalized))
assert (ds_2_non_finalized - ds_3_non_finalized) > (ds_0_non_finalized - ds_1_non_finalized)

# Test justification after non-finalization streak
print(casper.get_deposit_size(1))
casper.vote(mk_vote(1, _th, _te, _se, t.k1))
print(casper.get_deposit_size(1))
assert casper.main_hash_justified()
assert not casper.votes__is_finalized(_se)

# Test finalization after non-finalization streak
current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)
casper.vote(mk_vote(1, _th, _te, _se, t.k1))
print(casper.get_deposit_size(1))
assert casper.main_hash_justified()
assert casper.votes__is_finalized(_se)

current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)
ds_after_finalize = casper.get_deposit_size(1)
assert ds_after_finalize > ds_3_non_finalized
print("Finalization gains: %.4f" % (ds_after_finalize / ds_3_non_finalized - 1))

# test multiple validators
induct_validator(s, casper, t.k2, 2000 * 10**18)
induct_validator(s, casper, t.k3, 2000 * 10**18)
induct_validator(s, casper, t.k4, 2000 * 10**18)
induct_validator(s, casper, t.k5, 2000 * 10**18)

# new validators not yet in total deposits
assert casper.get_deposit_size(1) == casper.get_total_curdyn_deposits()
casper.vote(mk_vote(1, _th, _te, _se, t.k1))
current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)
casper.vote(mk_vote(1, _th, _te, _se, t.k1))
current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)


print(abs(sum(map(casper.get_deposit_size, range(1, 6))) - casper.get_total_curdyn_deposits()))
assert abs(sum(map(casper.get_deposit_size, range(1, 6))) - casper.get_total_curdyn_deposits()) < 5
print("Validator induction works")
votes = [mk_vote(i, _th, _te, _se, k) for i, k in zip(range(1, 5), [t.k1, t.k2, t.k3, t.k4])]
for vote in votes:
    casper.vote(vote)
assert casper.main_hash_justified()
assert casper.votes__is_finalized(_se)

print("Epoch %s justified with 4/5 votes" % _te)
print("Epoch %s finalized with 4/5 votes" % _se)


for i in range(1, 6):
    print(casper.get_deposit_size(i))

assert casper.get_deposit_size(5) < \
    casper.get_deposit_size(2) == casper.get_deposit_size(3) == casper.get_deposit_size(4)

# Test logging out
casper.logout(mk_logout(1, _te, t.k1))
current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)

votes = [mk_vote(i, _th, _te, _se, k) for i, k in zip(range(1, 5), [t.k1, t.k2, t.k3, t.k4])]
for vote in votes:
    casper.vote(vote)
assert casper.main_hash_justified()
assert casper.votes__is_finalized(_se)
print("Epoch %s justified with 4/5 votes" % _te)
print("Epoch %s finalized with 4/5 votes" % _se)

current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)
assert abs(sum(map(casper.get_deposit_size, range(2, 6))) - casper.get_total_curdyn_deposits()) < 5
assert abs(sum(map(casper.get_deposit_size, range(1, 6))) - casper.get_total_prevdyn_deposits()) < 5

votes = [mk_vote(i, _th, _te, _se, k) for i, k in zip(range(1, 5), [t.k1, t.k2, t.k3, t.k4])]
for vote in votes:
    casper.vote(vote)
assert casper.main_hash_justified()
assert casper.votes__is_finalized(_se)
print("Epoch %s justified with 4/5 votes" % _te)
print("Epoch %s finalized with 4/5 votes" % _se)

current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)
assert abs(sum(map(casper.get_deposit_size, range(2, 6))) - casper.get_total_curdyn_deposits()) < 5
assert abs(sum(map(casper.get_deposit_size, range(2, 6))) - casper.get_total_prevdyn_deposits()) < 5
print("Verified post-deposit logouts")

# Test only a portion of validators are online
for i in range(100):
    current_dyn, _th, _te, _se = new_epoch(s, casper, EPOCH_LENGTH)
    votes = [mk_vote(index, _th, _te, _se, k) for index, k in zip([2, 3], [t.k2, t.k3])]
    for vote in votes:
        casper.vote(vote)
    print(casper.get_main_hash_voted_frac())
    assert abs(sum(map(casper.get_deposit_size, range(2, 6))) - casper.get_total_curdyn_deposits()) < 5
    assert abs(sum(map(casper.get_deposit_size, range(2, 6))) - casper.get_total_prevdyn_deposits()) < 5

    # online percentage voted
    ovp = (casper.get_deposit_size(2) + casper.get_deposit_size(3)) / casper.get_total_curdyn_deposits()
    print("Epoch %d, online validator portion %.4f" % (_te, ovp))
    if ovp >= 0.75:
        assert casper.main_hash_justified()
        assert casper.votes__is_finalized(_se)
        break

print("Deposits of onilne validators: %d %d" % (casper.get_deposit_size(2), casper.get_deposit_size(3)))
print("Deposits of offline validators: %d %d" % (casper.get_deposit_size(4), casper.get_deposit_size(5)))
print("Tests passed")
