from ethereum.tools import tester as t
from ethereum import utils, common, transactions, abi
from casper_tester_helper_functions import mk_initializers, casper_config, new_epoch, custom_chain, \
    viper_rlp_decoder_address, sig_hasher_address, purity_checker_address, purity_checker_abi, \
    mk_vote, deploy_test_rlp
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

code_template = """
~calldatacopy(0, 0, 128)
~call(3000, 1, 0, 0, 128, 0, 32)
return(~mload(0) == %s)
"""


def mk_validation_code(address):
    return serpent.compile(code_template % (utils.checksum_encode(address)))


# Install Casper, RLP decoder, purity checker, sighasher
casper_address, casper_abi = mk_initializers(casper_config, s, t.k0)

ct = abi.ContractTranslator(purity_checker_abi)
# Check that the RLP decoding library and the sig hashing library are "pure"
assert utils.big_endian_to_int(s.tx(t.k0, purity_checker_address, 0, ct.encode('submit', [viper_rlp_decoder_address]))) == 1
assert utils.big_endian_to_int(s.tx(t.k0, purity_checker_address, 0, ct.encode('submit', [sig_hasher_address]))) == 1
print("Sig hasher deployed at %s" % sig_hasher_address)


casper = t.ABIContract(s, casper_abi, casper_address)
s.mine(1)

print(viper_rlp_decoder_address)
print(viper_utils.RLP_DECODER_ADDRESS)
assert viper_utils.bytes_to_int(viper_rlp_decoder_address) == viper_utils.RLP_DECODER_ADDRESS

print("Casper Contract deployed at: %s" % (casper_address))

rlp_abi, rlp_addr = deploy_test_rlp(s, t.k0)
rlp = t.ABIContract(s, rlp_abi, rlp_addr)
print("CHECK RLP SHOULD EQUAL 4: %s" %rlp.fos())

# Helper functions for making a prepare, commit, login and logout message

def mk_prepare(validator_index, epoch, ancestry_hash, source_epoch, source_ancestry_hash, key):
    sighash = utils.sha3(rlp.encode([validator_index, epoch, ancestry_hash, source_epoch, source_ancestry_hash]))
    v, r, s = utils.ecdsa_raw_sign(sighash, key)
    sig = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
    return rlp.encode([validator_index, epoch, ancestry_hash, source_epoch, source_ancestry_hash, sig])

def mk_commit(validator_index, epoch, hash, prev_commit_epoch, key):
    sighash = utils.sha3(rlp.encode([validator_index, epoch, hash, prev_commit_epoch]))
    v, r, s = utils.ecdsa_raw_sign(sighash, key)
    sig = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
    return rlp.encode([validator_index, epoch, hash, prev_commit_epoch, sig])

def mk_logout(validator_index, epoch, key):
    sighash = utils.sha3(rlp.encode([validator_index, epoch]))
    v, r, s = utils.ecdsa_raw_sign(sighash, key)
    sig = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
    return rlp.encode([validator_index, epoch, sig])

def induct_validator(casper, key, value):
    valcode_addr = s.tx(key, "", 0, mk_validation_code(utils.privtoaddr(key)))
    assert utils.big_endian_to_int(s.tx(key, purity_checker_address, 0, ct.encode('submit', [valcode_addr]))) == 1
    casper.deposit(valcode_addr, utils.privtoaddr(key), value=value)

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
induct_validator(casper, t.k1, VAL_1_DEPOSIT_SIZE)
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
if False:
    # Initialize the fifth epoch
    current_dyn, _e, _se, _th = new_epoch(s, casper, EPOCH_LENGTH)
    print(casper.get_latest_npf(), casper.get_latest_ncf(), casper.get_latest_resize_factor())
    print('pre deposit', casper.get_deposit_size(0))
    assert casper.get_total_curdyn_deposits() == casper.get_deposit_size(0)
    print("Fourth epoch prepared and committed, fifth epoch initialized")
    # Test the NO_DBL_PREPARE slashing condition
    p1 = mk_prepare(0, _e, _a, _se, _sa, t.k1)
    p2 = mk_prepare(0, _e, _sa, _se, _sa, t.k1)
    snapshot = s.snapshot()
    casper.double_prepare_slash(p1, p2)
    s.revert(snapshot)
    print("NO_DBL_PREPARE slashing condition works")
    # Test the PREPARE_COMMIT_CONSISTENCY slashing condition
    p3 = mk_prepare(0, _e, _a, 0, casper.get_ancestry_hashes(0), t.k1)
    snapshot = s.snapshot()
    casper.prepare_commit_inconsistency_slash(p3, epoch_4_commit)
    s.revert(snapshot)
    print("PREPARE_COMMIT_CONSISTENCY slashing condition works")
    # Finish the fifth epoch
    casper.prepare(p1)
    casper.commit(mk_commit(0, _e, _a, 4, t.k1))
    assert casper.get_main_hash_justified()
    assert casper.get_main_hash_finalized()
    ds_0_non_finalized = casper.get_deposit_size(0)
    current_dyn, _e, _se, _th = new_epoch(s, casper, EPOCH_LENGTH)
    ds_1_non_finalized = casper.get_deposit_size(0)
    print("Non-finalization losses (first epoch): %.4f" % (1 - ds_1_non_finalized / ds_0_non_finalized))
    assert ds_1_non_finalized < ds_0_non_finalized
    current_dyn, _e, _se, _th = new_epoch(s, casper, EPOCH_LENGTH)
    ds_2_non_finalized = casper.get_deposit_size(0)
    print("Non-finalization losses (second epoch): %.4f" % (1 - ds_2_non_finalized / ds_1_non_finalized))
    current_dyn, _e, _se, _th = new_epoch(s, casper, EPOCH_LENGTH)
    ds_3_non_finalized = casper.get_deposit_size(0)
    print("Non-finalization losses (third epoch): %.4f" % (1 - ds_3_non_finalized / ds_2_non_finalized))
    assert (ds_2_non_finalized - ds_3_non_finalized) > (ds_0_non_finalized - ds_1_non_finalized)
    print(casper.get_deposit_size(0))
    p4 = mk_prepare(0, _e, _a, _se, _sa, t.k1)
    casper.prepare(p4)
    print(casper.get_deposit_size(0))
    p4 = mk_prepare(0, _e, _a, _se, _sa, t.k1)
    c4 = mk_commit(0, _e, _a, 5, t.k1)
    casper.commit(c4)
    print(casper.get_deposit_size(0))
    p4 = mk_prepare(0, _e, _a, _se, _sa, t.k1)
    assert casper.get_main_hash_finalized()
    current_dyn, _e, _se, _th = new_epoch(s, casper, EPOCH_LENGTH)
    print(casper.get_latest_npf(), casper.get_latest_ncf(), casper.get_latest_resize_factor())
    print(casper.get_deposit_size(0), casper.get_current_penalty_factor())
    ds_after_finalize = casper.get_deposit_size(0)
    assert casper.get_latest_npf() < 0.1 and casper.get_latest_ncf() < 0.1
    assert ds_after_finalize > ds_3_non_finalized
    print("Finalization gains: %.4f" % (ds_after_finalize / ds_3_non_finalized - 1))
    induct_validator(casper, t.k2, 200 * 10**18)
    induct_validator(casper, t.k3, 200 * 10**18)
    induct_validator(casper, t.k4, 200 * 10**18)
    induct_validator(casper, t.k5, 200 * 10**18)
    assert casper.get_deposit_size(0) == casper.get_total_curdyn_deposits()
    p4 = mk_prepare(0, _e, _a, _se, _sa, t.k1)
    casper.prepare(p4)
    c4 = mk_commit(0, _e, _a, 8, t.k1)
    casper.commit(c4)
    current_dyn, _e, _se, _th = new_epoch(s, casper, EPOCH_LENGTH)
    p4 = mk_prepare(0, _e, _a, _se, _sa, t.k1)
    casper.prepare(p4)
    c4 = mk_commit(0, _e, _a, 9, t.k1)
    casper.commit(c4)
    current_dyn, _e, _se, _th = new_epoch(s, casper, EPOCH_LENGTH)
    assert abs(sum(map(casper.get_deposit_size, range(5))) - casper.get_total_curdyn_deposits()) < 5
    print("Validator induction works")
    for prepare in [mk_prepare(i, _e, _a, _se, _sa, k) for i, k in zip([0,1,2,3], [t.k1, t.k2, t.k3, t.k4])]:
        casper.prepare(prepare)
    assert casper.get_main_hash_justified()
    for commit in [mk_commit(i, _e, _a, casper.get_validators__prev_commit_epoch(i), k) for i, k in zip([0,1,2,3], [t.k1, t.k2, t.k3, t.k4])]:
        casper.commit(commit)
    assert casper.get_main_hash_finalized()
    print("Epoch 11 finalized with 4/5 prepares/commits")
    casper.logout(mk_logout(0, 11, t.k1))

    current_dyn, _e, _se, _th = new_epoch(s, casper, EPOCH_LENGTH)
    assert casper.get_deposit_size(4) < \
        casper.get_deposit_size(1) == casper.get_deposit_size(2) == casper.get_deposit_size(3)

    for prepare in [mk_prepare(i, _e, _a, _se, _sa, k) for i, k in zip([0,1,2,3], [t.k1, t.k2, t.k3, t.k4])]:
        casper.prepare(prepare)
    assert casper.get_main_hash_justified()
    for commit in [mk_commit(i, _e, _a, casper.get_validators__prev_commit_epoch(i), k) for i, k in zip([1,2,3,4], [t.k2, t.k3, t.k4, t.k5])]:
        casper.commit(commit)
    assert casper.get_main_hash_finalized()

    print("Epoch 12 finalized with 4/5 prepares/commits")
    current_dyn, _e, _se, _th = new_epoch(s, casper, EPOCH_LENGTH)
    assert abs(sum(map(casper.get_deposit_size, range(1, 5))) - casper.get_total_curdyn_deposits()) < 5
    assert abs(sum(map(casper.get_deposit_size, range(5))) - casper.get_total_prevdyn_deposits()) < 5

    for prepare in [mk_prepare(i, _e, _a, _se, _sa, k) for i, k in zip([0,1,2,3], [t.k1, t.k2, t.k3, t.k4])]:
        casper.prepare(prepare)
    assert casper.get_main_hash_justified()
    for commit in [mk_commit(i, _e, _a, casper.get_validators__prev_commit_epoch(i), k) for i, k in zip([1,2,3,4], [t.k2, t.k3, t.k4, t.k5])]:
        casper.commit(commit)
    assert casper.get_main_hash_finalized()
    print("Epoch 13 finalized with 4/5 prepares/commits")

    current_dyn, _e, _se, _th = new_epoch(s, casper, EPOCH_LENGTH)
    assert abs(sum(map(casper.get_deposit_size, range(1, 5))) - casper.get_total_curdyn_deposits()) < 5
    assert abs(sum(map(casper.get_deposit_size, range(1, 5))) - casper.get_total_prevdyn_deposits()) < 5

    print("Verified post-deposit logouts")
    for i in range(15, 100):
        current_dyn, _e, _se, _th = new_epoch(s, casper, EPOCH_LENGTH)
        for prepare in [mk_prepare(i, _e, _a, _se, _sa, k) for i, k in zip([1,2], [t.k2, t.k3])]:
            casper.prepare(prepare)
        print(casper.get_main_hash_prepared_frac())
        assert abs(sum(map(casper.get_deposit_size, range(1, 5))) - casper.get_total_curdyn_deposits()) < 5
        assert abs(sum(map(casper.get_deposit_size, range(1, 5))) - casper.get_total_prevdyn_deposits()) < 5
        ovp = (casper.get_deposit_size(1) + casper.get_deposit_size(2)) / casper.get_total_curdyn_deposits()
        print("Epoch %d, online validator portion %.4f" % (i, ovp))
        if ovp >= 0.7:
            assert casper.get_main_hash_justified()
            break

    for commit in [mk_commit(i, _e, _a, casper.get_validators__prev_commit_epoch(i), k) for i, k in zip([1,2], [t.k2, t.k3])]:
        casper.commit(commit)

    assert casper.get_main_hash_finalized()
    assert casper.get_main_hash_committed_frac() >= 0.667
    print("Deposits of remaining validators: %d %d" % (casper.get_deposit_size(1), casper.get_deposit_size(2)))
    print("Deposits of offline validators: %d %d" % (casper.get_deposit_size(3), casper.get_deposit_size(4)))
    print("Tests passed")
