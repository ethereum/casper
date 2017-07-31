from ethereum.tools import tester as t
from ethereum import utils, common, transactions, abi
from casper_initiating_transactions import mk_initializers, casper_config, \
    viper_rlp_decoder_address, sig_hasher_address, purity_checker_address, casper_abi, purity_checker_abi
from viper import compiler
import serpent
from ethereum.slogging import LogRecorder, configure_logging, set_level
config_string = ':info,eth.vm.log:trace,eth.vm.op:trace,eth.vm.stack:trace,eth.vm.exit:trace,eth.pb.msg:trace,eth.pb.tx:debug'
#configure_logging(config_string=config_string)
import rlp
alloc = {}
for i in range(9):
    alloc[utils.int_to_addr(i)] = {'balance': 1}
alloc[t.a0] = {'balance': 10**22}
alloc[t.a1] = {'balance': 10**22}
s = t.Chain(alloc=alloc)
t.languages['viper'] = compiler.Compiler()
t.gas_limit = 9999999
t.STARTGAS = 2000000
s.mine(1)

EPOCH_LENGTH = casper_config["epoch_length"]

code_template = """
~calldatacopy(0, 0, 128)
~call(3000, 1, 0, 0, 128, 0, 32)
return(~mload(0) == %s)
"""

def mk_validation_code(address):
    return serpent.compile(code_template % (utils.checksum_encode(address)))

# Install Casper, RLP decoder, purity checker, sighasher
init_txs, casper_address = mk_initializers(casper_config, t.k0)
for tx in init_txs:
    if s.head_state.gas_used + tx.startgas > s.head_state.gas_limit:
        s.mine(1)
    s.direct_tx(tx)

ct = abi.ContractTranslator(purity_checker_abi)
# Check that the RLP decoding library and the sig hashing library are "pure"
assert utils.big_endian_to_int(s.tx(t.k0, purity_checker_address, 0, ct.encode('submit', [viper_rlp_decoder_address]))) == 1
assert utils.big_endian_to_int(s.tx(t.k0, purity_checker_address, 0, ct.encode('submit', [sig_hasher_address]))) == 1


casper = t.ABIContract(s, casper_abi, casper_address)
s.mine(1)

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
s.mine(EPOCH_LENGTH - s.head_state.block_number)
casper.initialize_epoch(1)
assert casper.get_nextValidatorIndex() == 0
assert casper.get_current_epoch() == 1
print("Epoch initialized")

# Deposit one validator
induct_validator(casper, t.k1, 200 * 10**18)
# Mine two epochs
s.mine(EPOCH_LENGTH * 3 - s.head_state.block_number)
casper.initialize_epoch(2)
casper.initialize_epoch(3)
assert casper.get_total_curdyn_deposits() == 200 * 10**18
assert casper.get_total_prevdyn_deposits() == 0

_e, _a, _se, _sa = \
    casper.get_current_epoch(), casper.get_recommended_ancestry_hash(), \
    casper.get_recommended_source_epoch(), casper.get_recommended_source_ancestry_hash()
print("Penalty factor: %.8f" % (casper.get_current_penalty_factor()))
# Send a prepare message
print('pre deposit', casper.get_deposit_size(0), casper.get_total_curdyn_deposits())
assert casper.get_deposit_size(0) == casper.get_total_curdyn_deposits()
casper.prepare(mk_prepare(0, _e, _a, _se, _sa, t.k1))
print('Gas consumed for a prepare: %d' % s.last_gas_used(with_tx=True))
sourcing_hash = utils.sha3(utils.encode_int32(_e) + _a + utils.encode_int32(_se) + _sa)
assert casper.get_consensus_messages__ancestry_hash_justified(_e, _a)
assert casper.get_main_hash_justified()
print("Prepare message processed")
try:
    casper.prepare(mk_prepare(0, 1, '\x35' * 32, '\x00' * 32, 0, '\x00' * 32, t.k0))
    success = True
except:
    success = False
assert not success
print("Prepare message fails the second time")
# Send a commit message
casper.commit(mk_commit(0, _e, _a, 0, t.k1))
print('post deposit', casper.get_deposit_size(0))
print('Gas consumed for a commit: %d' % s.last_gas_used(with_tx=True))
# Check that we committed
assert casper.get_main_hash_finalized()
print("Commit message processed")
# Initialize the fourth epoch 
s.mine(EPOCH_LENGTH * 4 - s.head_state.block_number)
casper.initialize_epoch(4)
# Check that the dynasty increased as expected
assert casper.get_dynasty() == 4
print(casper.get_total_prevdyn_deposits(), casper.get_total_curdyn_deposits())
print("Second epoch initialized, dynasty increased as expected")
_e, _a, _se, _sa = \
    casper.get_current_epoch(), casper.get_recommended_ancestry_hash(), \
    casper.get_recommended_source_epoch(), casper.get_recommended_source_ancestry_hash()
# Send a prepare message
print('pre deposit', casper.get_deposit_size(0), casper.get_total_curdyn_deposits())
assert casper.get_deposit_size(0) == casper.get_total_curdyn_deposits()
casper.prepare(mk_prepare(0, _e, _a, _se, _sa, t.k1))
assert casper.get_main_hash_justified()
# Send a commit message
epoch_4_commit = mk_commit(0, _e, _a, 3, t.k1)
casper.commit(epoch_4_commit)
print('post deposit', casper.get_deposit_size(0))
# Check that we committed
assert casper.get_main_hash_finalized()
# Initialize the fifth epoch
s.mine(EPOCH_LENGTH * 5 - s.head_state.block_number)
casper.initialize_epoch(5)
print(casper.get_latest_npf(), casper.get_latest_ncf(), casper.get_latest_resize_factor())
print('pre deposit', casper.get_deposit_size(0))
assert casper.get_total_curdyn_deposits() == casper.get_deposit_size(0)
print("Fourth epoch prepared and committed, fifth epoch initialized")
_e, _a, _se, _sa = \
    casper.get_current_epoch(), casper.get_recommended_ancestry_hash(), \
    casper.get_recommended_source_epoch(), casper.get_recommended_source_ancestry_hash()
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
s.mine(EPOCH_LENGTH * 6 - s.head_state.block_number)
casper.initialize_epoch(6)
ds_1_non_finalized = casper.get_deposit_size(0)
print("Non-finalization losses (first epoch): %.4f" % (1 - ds_1_non_finalized / ds_0_non_finalized))
assert ds_1_non_finalized < ds_0_non_finalized
s.mine(EPOCH_LENGTH * 7 - s.head_state.block_number)
casper.initialize_epoch(7)
ds_2_non_finalized = casper.get_deposit_size(0)
print("Non-finalization losses (second epoch): %.4f" % (1 - ds_2_non_finalized / ds_1_non_finalized))
s.mine(EPOCH_LENGTH * 8 - s.head_state.block_number)
casper.initialize_epoch(8)
ds_3_non_finalized = casper.get_deposit_size(0)
print("Non-finalization losses (third epoch): %.4f" % (1 - ds_3_non_finalized / ds_2_non_finalized))
assert (ds_2_non_finalized - ds_3_non_finalized) > (ds_0_non_finalized - ds_1_non_finalized)
_e, _a, _se, _sa = \
    casper.get_current_epoch(), casper.get_recommended_ancestry_hash(), \
    casper.get_recommended_source_epoch(), casper.get_recommended_source_ancestry_hash()
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
s.mine(EPOCH_LENGTH * 9 - s.head_state.block_number)
casper.initialize_epoch(9)
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
s.mine(1)
assert casper.get_deposit_size(0) == casper.get_total_curdyn_deposits()
_e, _a, _se, _sa = \
    casper.get_current_epoch(), casper.get_recommended_ancestry_hash(), \
    casper.get_recommended_source_epoch(), casper.get_recommended_source_ancestry_hash()
p4 = mk_prepare(0, _e, _a, _se, _sa, t.k1)
casper.prepare(p4)
c4 = mk_commit(0, _e, _a, 8, t.k1)
casper.commit(c4)
s.mine(EPOCH_LENGTH * 10 - s.head_state.block_number)
casper.initialize_epoch(10)
_e, _a, _se, _sa = \
    casper.get_current_epoch(), casper.get_recommended_ancestry_hash(), \
    casper.get_recommended_source_epoch(), casper.get_recommended_source_ancestry_hash()
p4 = mk_prepare(0, _e, _a, _se, _sa, t.k1)
casper.prepare(p4)
c4 = mk_commit(0, _e, _a, 9, t.k1)
casper.commit(c4)
s.mine(EPOCH_LENGTH * 11 - s.head_state.block_number)
casper.initialize_epoch(11)
assert abs(sum(map(casper.get_deposit_size, range(5))) - casper.get_total_curdyn_deposits()) < 5
print("Validator induction works")
_e, _a, _se, _sa = \
    casper.get_current_epoch(), casper.get_recommended_ancestry_hash(), \
    casper.get_recommended_source_epoch(), casper.get_recommended_source_ancestry_hash()
for prepare in [mk_prepare(i, _e, _a, _se, _sa, k) for i, k in zip([0,1,2,3], [t.k1, t.k2, t.k3, t.k4])]:
    casper.prepare(prepare)
assert casper.get_main_hash_justified()
s.mine(1)
for commit in [mk_commit(i, _e, _a, casper.get_validators__prev_commit_epoch(i), k) for i, k in zip([0,1,2,3], [t.k1, t.k2, t.k3, t.k4])]:
    casper.commit(commit)
assert casper.get_main_hash_finalized()
print("Epoch 11 finalized with 4/5 prepares/commits")
casper.logout(mk_logout(0, 11, t.k1))

s.mine(EPOCH_LENGTH * 12 - s.head_state.block_number)
casper.initialize_epoch(12)
assert casper.get_deposit_size(4) < \
    casper.get_deposit_size(1) == casper.get_deposit_size(2) == casper.get_deposit_size(3)

_e, _a, _se, _sa = \
    casper.get_current_epoch(), casper.get_recommended_ancestry_hash(), \
    casper.get_recommended_source_epoch(), casper.get_recommended_source_ancestry_hash()
for prepare in [mk_prepare(i, _e, _a, _se, _sa, k) for i, k in zip([0,1,2,3], [t.k1, t.k2, t.k3, t.k4])]:
    casper.prepare(prepare)
assert casper.get_main_hash_justified()
s.mine(1)
for commit in [mk_commit(i, _e, _a, casper.get_validators__prev_commit_epoch(i), k) for i, k in zip([1,2,3,4], [t.k2, t.k3, t.k4, t.k5])]:
    casper.commit(commit)
assert casper.get_main_hash_finalized()

print("Epoch 12 finalized with 4/5 prepares/commits")
s.mine(EPOCH_LENGTH * 13 - s.head_state.block_number)
casper.initialize_epoch(13)
assert abs(sum(map(casper.get_deposit_size, range(1, 5))) - casper.get_total_curdyn_deposits()) < 5
assert abs(sum(map(casper.get_deposit_size, range(5))) - casper.get_total_prevdyn_deposits()) < 5

_e, _a, _se, _sa = \
    casper.get_current_epoch(), casper.get_recommended_ancestry_hash(), \
    casper.get_recommended_source_epoch(), casper.get_recommended_source_ancestry_hash()
for prepare in [mk_prepare(i, _e, _a, _se, _sa, k) for i, k in zip([0,1,2,3], [t.k1, t.k2, t.k3, t.k4])]:
    casper.prepare(prepare)
assert casper.get_main_hash_justified()
s.mine(1)
for commit in [mk_commit(i, _e, _a, casper.get_validators__prev_commit_epoch(i), k) for i, k in zip([1,2,3,4], [t.k2, t.k3, t.k4, t.k5])]:
    casper.commit(commit)
assert casper.get_main_hash_finalized()
print("Epoch 13 finalized with 4/5 prepares/commits")

s.mine(EPOCH_LENGTH * 14 - s.head_state.block_number)
casper.initialize_epoch(14)
assert abs(sum(map(casper.get_deposit_size, range(1, 5))) - casper.get_total_curdyn_deposits()) < 5
assert abs(sum(map(casper.get_deposit_size, range(1, 5))) - casper.get_total_prevdyn_deposits()) < 5

print("Verified post-deposit logouts")
for i in range(15, 100):
    s.mine(EPOCH_LENGTH * i - s.head_state.block_number)
    casper.initialize_epoch(i)
    _e, _a, _se, _sa = \
        casper.get_current_epoch(), casper.get_recommended_ancestry_hash(), \
        casper.get_recommended_source_epoch(), casper.get_recommended_source_ancestry_hash()
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
