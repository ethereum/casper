# Not finished, needs to be properly hooked in
# Example code:
# J1 J2 J3 B B B S1 B B C1 B B B P1 P2 C1 C2 B S1 B B B
# Translates into:
# Join with validators 1, 2 and 3. Then create 3 blocks, save a
# checkpoint 1. Create 2 more blocks, then revert to checkpoint 1.
# Create 3 more blocks, then prepare and commit with validators
# 1 and 2. Finally create 3 more blocks.

from ethereum.hybrid_casper import chain
from ethereum.common import verify_execution_results, mk_block_from_prevstate, set_execution_results
from ethereum.utils import sha3
from <INSERT HERE> import casper_init_txs, validation_code_addr_from_privkey, call_casper
from <INSERT HERE> import Validator
import re

validator_lookup_map = {validation_code_addr_from_privkey(sha3(str(i))): i for i in range(20)}

def interpret_test(test):
    c = chain.Chain()
    b = mk_block_from_prevstate(c, timestamp=c.state.timestamp + 1)
    for tx in casper_init_txs:
        b.transactions.append(tx)
    
    c.add_block(b)
    head = c.head_hash
    validators = [Validator(privkey=sha3(str(i))) for i in range(20)]
    markers = {}
    txs = []
    
    for token in test.split(' '):
        letters, numbers = re.match('([A-Za-z]*)([0-9]*)', token).groups()
        if letters+numbers != token:
            raise Exception("Bad token: %s" % token)
        numbers = int(numbers)
        # Adds a block to the current head
        if letters == 'B':
            if head == c.head:
                b = mk_block_from_prevstate(c, timestamp=c.state.timestamp + 1)
            else:
                s = c.mk_poststate_of_blockhash(head)
                b = mk_block_from_prevstate(c, state=s, timestamp=s.timestamp + 1)
            b.txs = txs
            c.add_block(b)
            txs = []
        # Saves a marker (eg "S5" creates a marker called 5 and sets the current head to that)
        elif letters == 'S':
            self.markers[numbers] = head
        # Changes the head to a marker (eg "C5" changes the head to the marker 5)
        elif letters == 'C':
            assert len(txs) == 0
            head = self.markers[numbers]
        # Adds a join transaction to the tx list (eg. "J5" adds a join for validator 5)
        elif letters == 'J':
            txs.append(validators[numbers].mk_join_transaction())
        # Adds a prepare to the tx list (eg. "P5" adds a prepare for validator 5)
        elif letters == 'P':
            txs.append(validators[numbers].mk_prepare())
        # Adds a commit to the tx list (eg. "C5" adds a commit for validator 5)
        elif letters == 'C':
            txs.append(validators[numbers].mk_commit())

    on_longest_chain = head == c.head_hash
    balances = {}
    active = {}
    for i in range(100):
        validator_addr = call_casper(c.head_state, 'get_validator__addr', i)
        if validator_addr in validator_lookup_map:
            balances[validator_lookup_map[validator_addr]] = call_casper(c.head_state, 'get_validator__deposit', i)
            active[validator_lookup_map[validator_addr]] = call_casper(c.head_state, 'is_validator_active', i)
    epoch = call_casper(c.head_state, 'get_current_epoch')
    total_deposits = call_casper(c.head_state, 'get_total_deposits', epoch)
    return {
        'on_longest_chain': on_longest_chain,
        'balances': balances,
        'active': active,
        'total_deposits': total_deposits
    }
