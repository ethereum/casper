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
s.mine(1)

EPOCH_LENGTH = 10

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
    s.direct_tx(tx)
    s.mine(1)

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

# Begin the test

print("Starting tests")
# Initialize the first epoch
s.mine(EPOCH_LENGTH - s.head_state.block_number)
casper.initialize_epoch(1)
assert casper.get_nextValidatorIndex() == 0
assert casper.get_current_epoch() == 1
print("Epoch initialized")

# Deposit one validator
k1_valcode_addr = s.tx(t.k1, "", 0, mk_validation_code(t.a1))
assert utils.big_endian_to_int(s.tx(t.k1, purity_checker_address, 0, ct.encode('submit', [k1_valcode_addr]))) == 1
casper.deposit(k1_valcode_addr, utils.privtoaddr(t.k1), value=200 * 10**18)
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
print(casper.get_latest_npf(), casper.get_latest_ncf(), casper.get_latest_interest())
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
# Finish the third epoch
casper.prepare(p1)
casper.commit(mk_commit(0, _e, _a, 4, t.k1))
assert casper.get_main_hash_justified()
assert casper.get_main_hash_finalized()

print("Restarting the chain for test 2")
# Restart the chain
s.revert(start)
assert casper.get_dynasty() == 0
assert casper.get_current_epoch() == 1
assert casper.get_consensus_messages__ancestry_hash_justified(0, b'\x00' * 32)
print("Epoch 1 initialized")
for k in (t.k1, t.k2, t.k3, t.k4, t.k5, t.k6):
    valcode_addr = s.send(t.k0, '', 0, mk_validation_code(utils.privtoaddr(k)))
    assert utils.big_endian_to_int(s.send(t.k0, purity_checker_address, 0, ct.encode('submit', [valcode_addr]))) == 1
    casper.deposit(valcode_addr, utils.privtoaddr(k), value=3 * 10**18)
print("Processed 6 deposits")
casper.prepare(mk_prepare(0, 1, b'\x10' * 32, b'\x00' * 32, 0, b'\x00' * 32, t.k0))
casper.commit(mk_commit(0, 1, b'\x10' * 32, 0, t.k0))
epoch_1_anchash = utils.sha3(b'\x10' * 32 + b'\x00' * 32)
assert casper.get_consensus_messages__committed(1)
print("Prepared and committed")
s.state.block_number += EPOCH_LENGTH
casper.initialize_epoch(2)
print("Epoch 2 initialized")
assert casper.get_dynasty() == 1
casper.prepare(mk_prepare(0, 2, b'\x20' * 32, epoch_1_anchash, 1, epoch_1_anchash, t.k0))
casper.commit(mk_commit(0, 2, b'\x20' * 32, 1, t.k0))
epoch_2_anchash = utils.sha3(b'\x20' * 32 + epoch_1_anchash)
assert casper.get_consensus_messages__committed(2)
print("Confirmed that one key is still sufficient to prepare and commit")
s.state.block_number += EPOCH_LENGTH
casper.initialize_epoch(3)
print("Epoch 3 initialized")
assert casper.get_dynasty() == 2
assert 3 * 10**18 <= casper.get_total_deposits(0) < 4 * 10**18
assert 3 * 10**18 <= casper.get_total_deposits(1) < 4 * 10**18
assert 21 * 10**18 <= casper.get_total_deposits(2) < 22 * 10**18
print("Confirmed new total_deposits")
try:
    # Try to log out, but sign with the wrong key
    casper.flick_status(mk_status_flicker(0, 3, 0, t.k1))
    success = True
except:
    success = False
assert not success
# Log out
casper.flick_status(mk_status_flicker(4, 3, 0, t.k4))
casper.flick_status(mk_status_flicker(5, 3, 0, t.k5))
casper.flick_status(mk_status_flicker(6, 3, 0, t.k6))
print("Logged out three validators")
# Validators leave the fwd validator set in dynasty 4
assert casper.get_validators__dynasty_end(4) == 4
epoch_3_anchash = utils.sha3(b'\x30' * 32 + epoch_2_anchash)
# Prepare from one validator
casper.prepare(mk_prepare(0, 3, b'\x30' * 32, epoch_2_anchash, 2, epoch_2_anchash, t.k0))
# Not prepared yet
assert not casper.get_consensus_messages__hash_justified(3, b'\x30' * 32)
print("Prepare from one validator no longer sufficient")
# Prepare from 3 more validators
for i, k in ((1, t.k1), (2, t.k2), (3, t.k3)):
    casper.prepare(mk_prepare(i, 3, b'\x30' * 32, epoch_2_anchash, 2, epoch_2_anchash, k))
# Still not prepared
assert not casper.get_consensus_messages__hash_justified(3, b'\x30' * 32)
print("Prepare from four of seven validators still not sufficient")
# Prepare from a fifth validator
casper.prepare(mk_prepare(4, 3, b'\x30' * 32, epoch_2_anchash, 2, epoch_2_anchash, t.k4))
# NOW we're prepared!
assert casper.get_consensus_messages__hash_justified(3, b'\x30' * 32)
print("Prepare from five of seven validators sufficient!")
# Five commits
for i, k in enumerate([t.k0, t.k1, t.k2, t.k3, t.k4]):
    casper.commit(mk_commit(i, 3, b'\x30' * 32, 2 if i == 0 else 0, k))
# And we committed!
assert casper.get_consensus_messages__committed(3)
print("Commit from five of seven validators sufficient")
# Start epoch 4
s.state.block_number += EPOCH_LENGTH
casper.initialize_epoch(4)
assert casper.get_dynasty() == 3
print("Epoch 4 initialized")
# Prepare and commit
epoch_4_anchash = utils.sha3(b'\x40' * 32 + epoch_3_anchash)
for i, k in enumerate([t.k0, t.k1, t.k2, t.k3, t.k4]):
    casper.prepare(mk_prepare(i, 4, b'\x40' * 32, epoch_3_anchash, 3, epoch_3_anchash, k))
for i, k in enumerate([t.k0, t.k1, t.k2, t.k3, t.k4]):
    casper.commit(mk_commit(i, 4, b'\x40' * 32, 3, k))
assert casper.get_consensus_messages__committed(4)
print("Prepared and committed")
# Start epoch 5 / dynasty 4
s.state.block_number += EPOCH_LENGTH
casper.initialize_epoch(5)
print("Epoch 5 initialized")
assert casper.get_dynasty() == 4
assert 21 * 10**18 <= casper.get_total_deposits(3) <= 22 * 10**18
assert 12 * 10**18 <= casper.get_total_deposits(4) <= 13 * 10**18
epoch_5_anchash = utils.sha3(b'\x50' * 32 + epoch_4_anchash)
# Do three prepares
for i, k in enumerate([t.k0, t.k1, t.k2]):
    casper.prepare(mk_prepare(i, 5, b'\x50' * 32, epoch_4_anchash, 4, epoch_4_anchash, k))
# Three prepares are insufficient because there are still five validators in the rear validator set
assert not casper.get_consensus_messages__hash_justified(5, b'\x50' * 32)
print("Three prepares insufficient, as rear validator set still has seven")
# Do two more prepares
for i, k in [(3, t.k3), (4, t.k4)]:
    casper.prepare(mk_prepare(i, 5, b'\x50' * 32, epoch_4_anchash, 4, epoch_4_anchash, k))
# Now we're good!
assert casper.get_consensus_messages__hash_justified(5, b'\x50' * 32)
print("Five prepares sufficient")
for i, k in enumerate([t.k0, t.k1, t.k2, t.k3, t.k4]):
    casper.commit(mk_commit(i, 5, b'\x50' * 32, 4, k))
# Committed!
assert casper.get_consensus_messages__committed(5)
# Start epoch 6 / dynasty 5
s.state.block_number += EPOCH_LENGTH
casper.initialize_epoch(6)
assert casper.get_dynasty() == 5
print("Epoch 6 initialized")
# Log back in
old_deposit_start = casper.get_dynasty_start_epoch(casper.get_validators__dynasty_start(4))
old_deposit_end = casper.get_dynasty_start_epoch(casper.get_validators__dynasty_end(4) + 1)
old_deposit = casper.get_validators__deposit(4)
# Explanation:
# * During dynasty 0, the validator deposited, so he joins the current set in dynasty 2
#   (epoch 3), and the previous set in dynasty 3 (epoch 4)
# * During dynasty 2, the validator logs off, so he leaves the current set in dynasty 4
#   (epoch 5) and the previous set in dynasty 5 (epoch 6)
assert [casper.check_eligible_in_epoch(4, i) for i in range(7)] == [0, 0, 0, 2, 3, 1, 0]
casper.flick_status(mk_status_flicker(4, 6, 1, t.k4))
# Explanation:
# * During dynasty 7, the validator will log on again. Hence, the dynasty mask 
#   should include dynasties 4, 5, 6
assert [casper.check_eligible_in_epoch(4, i) for i in range(7)] == [0, 0, 0, 2, 3, 1, 0]
new_deposit = casper.get_validators__deposit(4)
print("One validator logging back in")
print("Penalty from %d epochs: %.4f" % (old_deposit_end - old_deposit_start, 1 - new_deposit / old_deposit))
assert casper.get_validators__dynasty_start(4) == 7
# Here three prepares and three commits should be sufficient!
epoch_6_anchash = utils.sha3(b'\x60' * 32 + epoch_5_anchash)
for i, k in enumerate([t.k0, t.k1, t.k2]):
    casper.prepare(mk_prepare(i, 6, b'\x60' * 32, epoch_5_anchash, 5, epoch_5_anchash, k))
for i, k in enumerate([t.k0, t.k1, t.k2]):
    casper.commit(mk_commit(i, 6, b'\x60' * 32, 5, k))
assert casper.get_consensus_messages__committed(6)
print("Three of four prepares and commits sufficient")
# Start epoch 7 / dynasty 6
s.state.block_number += EPOCH_LENGTH
casper.initialize_epoch(7)
assert casper.get_dynasty() == 6
print("Epoch 7 initialized")
# Here three prepares and three commits should be sufficient!
epoch_7_anchash = utils.sha3(b'\x70' * 32 + epoch_6_anchash)
for i, k in enumerate([t.k0, t.k1, t.k2]):
    #if i == 1:
    #    configure_logging(config_string=config_string)
    casper.prepare(mk_prepare(i, 7, b'\x70' * 32, epoch_6_anchash, 6, epoch_6_anchash, k))
    #if i == 1:
    #    import sys
    #    sys.exit()
print('Gas consumed for first prepare', s.state.receipts[-1].gas_used - s.state.receipts[-2].gas_used)
print('Gas consumed for second prepare', s.state.receipts[-2].gas_used - s.state.receipts[-3].gas_used)
print('Gas consumed for third prepare', s.state.receipts[-3].gas_used - s.state.receipts[-4].gas_used)
for i, k in enumerate([t.k0, t.k1, t.k2]):
    casper.commit(mk_commit(i, 7, b'\x70' * 32, 6, k))
print('Gas consumed for first commit', s.state.receipts[-1].gas_used - s.state.receipts[-2].gas_used)
print('Gas consumed for second commit', s.state.receipts[-2].gas_used - s.state.receipts[-3].gas_used)
print('Gas consumed for third commit', s.state.receipts[-3].gas_used - s.state.receipts[-4].gas_used)
assert casper.get_consensus_messages__committed(7)
print("Three of four prepares and commits sufficient")
# Start epoch 8 / dynasty 7
s.state.block_number += EPOCH_LENGTH
casper.initialize_epoch(8)
assert casper.get_dynasty() == 7
print("Epoch 8 initialized")
assert 12 * 10**18 <= casper.get_total_deposits(6) <= 13 * 10**18
assert 15 * 10**18 <= casper.get_total_deposits(7) <= 16 * 10**18
epoch_8_anchash = utils.sha3(b'\x80' * 32 + epoch_7_anchash)
# Do three prepares
for i, k in enumerate([t.k0, t.k1, t.k2]):
    casper.prepare(mk_prepare(i, 8, b'\x80' * 32, epoch_7_anchash, 7, epoch_7_anchash, k))
# Three prepares are insufficient because there are still five validators in the rear validator set
assert not casper.get_consensus_messages__hash_justified(8, b'\x80' * 32)
print("Three prepares no longer sufficient, as the forward validator set has five validators")
# Do one more prepare
for i, k in [(3, t.k3)]:
    casper.prepare(mk_prepare(i, 8, b'\x80' * 32, epoch_7_anchash, 7, epoch_7_anchash, k))
# Now we're good!
assert casper.get_consensus_messages__hash_justified(8, b'\x80' * 32)
print("Four of five prepares sufficient")
for i, k in enumerate([t.k0, t.k1, t.k2, t.k3, t.k4]):
    casper.commit(mk_commit(i, 8, b'\x80' * 32, 7 if i < 3 else 5, k))
assert casper.get_consensus_messages__committed(8)
print("Committed")
# Validator rejoins current validator set in epoch 8
assert [casper.check_eligible_in_epoch(4, i) for i in range(9)] == [0, 0, 0, 2, 3, 1, 0, 0, 2]

print("All tests passed")
