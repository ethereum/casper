
## Background
In this proposed spec for stage 1 Casper, Ethereum will transition from pure proof of work to hybrid PoW/PoS. In this scheme, all of the proof of work mechanics will continue to exist albeit with a reduced block reward (0.6 ETH), but additional proof of stake mechanisms will be added. In particular, the fork choice rule (ie. the way that a client determines which chain is &#34;the canonical chain&#34;) will be modified to take these mechanics into account.

A &#34;Casper contract&#34; will be published at some address `CASPER_ADDR`, and this contract will include functionality that allows anyone to deposit their ether, specifying a piece of &#34;validation code&#34; (think of this as being kind of like a public key) that they will use to sign messages, and become a validator. Once a user is inducted into the active validator pool, they will be able to send messages to participate in the PoS consensus process. The &#34;size&#34; of a validator in the active validator pool refers to the amount of ether that they deposited.

The purpose of the PoS consensus process is to &#34;finalize&#34; key blocks called &#34;checkpoints&#34;. Every 50th block is a checkpoint. To finalize a checkpoint, `2/3rds` of validator deposits must vote on two _sequential_ checkpoints. This finalizes the first of the two checkpoints. For more information regarding the Casper consensus protocol see [the paper here](https://github.com/ethereum/research/blob/master/papers/casper-basics/casper_basics.pdf).

### Casper Resources
- [Proof of Stake FAQ](https://github.com/ethereum/wiki/wiki/Proof-of-Stake-FAQ)
- [Casper FFG paper](https://arxiv.org/abs/1710.09437)
- [Jon Choi’s Casper 101](https://medium.com/@jonchoi/ethereum-casper-101-7a851a4f1eb0)
- [Presentation by Karl Floersch](https://www.youtube.com/watch?v=ycF0WFHY5kc)

## Outline

This document outlines the different components which make up the Casper implementation. These include the:
- Validator workflow overview,
- `simple_casper` contract,
- Fork choice rule modification,
- Epoch initialization logic,
- Casper transaction gas refunds,
- Block ordering, and
- Simple validator voting logic.

## Validator Workflow Overview
1. [Create valcode:](http://notes.ethresear.ch/GwTgLAZghgRgHGAtABmARgKaLFNzEIwjZgDsAxsBAMzIwbJpA===?both#validation-code)
    - Deploy a new contract which is used to validate a validator&#39;s signature.
2. Submit Deposit:
    - Call `casper.deposit(validation_addr, withdrawal_addr)` passing in the validation code contract address from step (1) and your withdrawal address.
3. **[Once each Epoch]** [Submit new vote message:](http://notes.ethresear.ch/GwTgLAZghgRgHGAtABmARgKaLFNzEIwjZgDsAxsBAMzIwbJpA===?both#casper-vote-generation)
    - Wait to vote until the checkpoint is at least `EPOCH_LENGTH/4` blocks deep in the main chain. This ensures all validators vote on the same block.
    - Generate unsigned vote message based on your chain&#39;s current head.
    - Broadcast the unsigned vote transaction to the network.
4. Logout:
    - [Submit logout message.](http://notes.ethresear.ch/GwTgLAZghgRgHGAtABmARgKaLFNzEIwjZgDsAxsBAMzIwbJpA===?both#logout-message-generation)
    - Call `casper.logout(logout_msg)` passing in your newly generated logout message.
5. Withdraw:
    - Call `casper.withdraw(validator_index)` and your funds will be sent to your validator&#39;s withdrawal address specified in step (2).

## Validator States
Validators are highly stateful. They must handle valcode creation, depositing, voting, and logging out. Each stage also requires waiting for transaction confirmations. Because of this complexity, a mapping of state to handler is used.

The validator state mapping [implemented in pyethapp](https://github.com/karlfloersch/pyethapp/blob/dev_env/pyethapp/validator_service.py#L58-L67) is as follows:
```
uninitiated: self.check_status,
waiting_for_valcode: self.check_valcode,
waiting_for_login: self.check_status,
voting: self.vote,
waiting_for_log_out: self.vote_then_logout,
waiting_for_withdrawable: self.check_withdrawable,
waiting_for_withdrawn: self.check_withdrawn,
logged_out: self.check_status
```

### Validator State Transition Diagram
![ffg-validator](https://user-images.githubusercontent.com/706123/34855668-d2f55412-f6f5-11e7-8d83-370ffe65a9b8.png)
Arrows are the logic followed upon receiving a new block while in a given state. For example, if the validator is in state `voting` and receives a new block whose height is `in_first_quarter_of_epoch`, then the validator follows the arrow to remain in the state `voting`.

## Validation Code
Validators must deploy their own signature validation contract. This will be used to check the signatures attached to their votes. This validation code **must** be a pure function. This means no storage reads/writes, environment variable reads OR external calls (except to other contracts that have already been purity-verified, or to precompiles) allowed.

For basic signature verification, [ecdsa signatures are currently being used](https://github.com/karlfloersch/pyethereum/blob/develop/ethereum/hybrid_casper/casper_utils.py#L75). The validation code for these ecdsa signatures can be found [here](https://github.com/ethereum/casper/blob/34503973abceed0f0267fe35e229a40e7a94270a/casper/contracts/sighash.se.py).

The validation code contract is currently being deployed as a part of the `induct_validator()` function [found here](https://github.com/karlfloersch/pyethereum/blob/develop/ethereum/hybrid_casper/casper_utils.py#L85-L89):
```
def induct_validator(chain, casper, key, value):
    sender = utils.privtoaddr(key)
    valcode_addr = chain.tx(key, "", 0, mk_validation_code(sender))  # Create a new validation code contract based on the validator's Ethereum address
    assert utils.big_endian_to_int(chain.tx(key, purity_checker_address, 0, purity_translator.encode('submit', [valcode_addr]))) == 1
    casper.deposit(valcode_addr, sender, value=value)  # Submit deposit specifying the validation code contract address
```

## Casper Vote Format
A Casper vote is an RLP-encoded list with the elements:
```
[
  validator_index: number,  # Index of the validator sending this vote
  target_hash: bytes32,  # Hash of the target checkpoint block for this vote
  target_epoch: number,  # Epoch number of the target checkpoint
  source_epoch: number,  # Epoch number of the source checkpoint
  signature  # A signed hash of the first four elements in this list, RLP encoded. (ie. RLP([validator_index, target_hash, target_epoch, source_epoch])
]
```
Casper vote messages are simply included in normal transactions sent to the Casper contract&#39;s `casper.vote(vote_msg)` function.

## Casper Vote Generation
To generate a Casper vote which votes on your chain&#39;s current head, first get the vote message contents. To do this, using the Casper contract call:
- `casper.validator_indexes(WITHDRAWAL_ADDRESS)` for the `validator_index`
- `casper.recommended_target_hash()` for the `target_hash`
- `casper.current_epoch()` for the `target_epoch`
- `casper.recommended_source_epoch()` for the `source_epoch`

Next, RLP encode all these elements. To compute your signature, compute the `sha3` hash of your vote&#39;s RLP encoded list, and sign the hash. Your signature must be valid when checked against your validator&#39;s `validation_code` contract. Finally, append your signature to the end of the vote message contents.

This is [implemented in Pyethereum](https://github.com/karlfloersch/pyethereum/blob/develop/ethereum/hybrid_casper/casper_utils.py#L73-L77) as follows:
```
def mk_vote(validator_index, target_hash, target_epoch, source_epoch, key):
    sighash = utils.sha3(rlp.encode([validator_index, target_hash, target_epoch, source_epoch]))
    v, r, s = utils.ecdsa_raw_sign(sighash, key)
    sig = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
    return rlp.encode([validator_index, target_hash, target_epoch, source_epoch, sig])
```

## Logout Message Generation
Like the Casper vote messages, a logout message is an RLP encoded list where the last element is the validator&#39;s signature. The elements of the unsigned list are the `validator_index` and `epoch` where epoch is the current epoch. A signature is generated in the same way it is done with votes above.

This is [implemented in Pyethereum](https://github.com/karlfloersch/pyethereum/blob/develop/ethereum/hybrid_casper/casper_utils.py#L79-L83) as follows:
```
def mk_logout(validator_index, epoch, key):
    sighash = utils.sha3(rlp.encode([validator_index, epoch]))
    v, r, s = utils.ecdsa_raw_sign(sighash, key)
    sig = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
    return rlp.encode([validator_index, epoch, sig])
```

## Simple Casper Contract High Level Overview
The Casper smart contract contains Casper&#39;s core logic. It is written in Vyper &amp; can be deployed to the blockchain like any other contract to `CASPER_ADDR`. Casper messages are then sent to the contract by calling `vote(vote_msg)` where `vote_msg` is a Casper vote messaged as outlined above.

### [[Contract Source]](https://github.com/ethereum/casper/blob/master/casper/contracts/simple_casper.v.py)

#### `def __init__(epoch_length, withdrawal_delay, ...)`
The Casper contract constructor takes in key settings. Most notably: 
- `epoch_length`
- `withdrawal_delay`
- `dynasty_logout_delay`
- `min_deposit_size`
- `base_interest_factor`
- `base_penalty_factor`

These settings cannot be changed after deployment.

#### `def initialize_epoch(epoch)`
Calculates the interest rate &amp; penalty factor for this epoch based on the time since finality.

Once a new epoch begins, this function is immediately called as the first transaction applied to the state. See [Epoch initialization](http://notes.eth.sg/GwTgLAZghgRgHGAtABmARgKaLFNzEIwjZgDsAxsBAMzIwbJpA===?both#epoch-initialization) for more details.

#### `def deposit(validation_addr, withdrawal_addr)`
Accepts deposits from prospective validators &amp; adds them to the next validator set.

#### `def logout(logout_msg)`
Initiates validator logout. The validator must continue to validate for `dynasty_logout_delay` dynasties before entering the `withdrawal_delay` waiting period.

#### `def withdraw(validator_index)`
If the validator has waited for a period greater than `withdrawal_delay` epochs past their `end_dynasty`, then send them ETH equivalent to their deposit.

#### `def vote(vote_msg)`
Called once by each validator each epoch. The vote message contains the fields presented in [Casper Vote Format](http://notes.eth.sg/GwTgLAZghgRgHGAtABmARgKaLFNzEIwjZgDsAxsBAMzIwbJpA===?both#casper-vote-format).

#### `def slash(vote_msg_1, vote_msg_2)`
Can be called by anyone who detects a slashing condition violation. Sends 4% of slashed validator&#39;s funds to the caller as a finder&#39;s fee and burns the remaining 96%.

## Casper Fork Choice Rule
The Casper fork choice rule is as follows:
1. Start with last finalized checkpoint
2. From that finalized checkpoint, select the casper checkpoint with the highest justified epoch: `casper.last_justified_epoch()`
3. Starting from that justified checkpoint, choose the block with the highest PoW score as the new head

Checkpoints are not considered finalized from a client perspective if the validators&#39; total_deposits is less than `NON_REVERT_MIN_DEPOSIT`. This var is configurable clientside depending on local security requirements.

The fork choice is roughly implemented with the following ([pyethereum implementation here](https://github.com/karlfloersch/pyethereum/blob/develop/ethereum/hybrid_casper/chain.py#L201-L249)):

```python
def add_block(self, candidate_block):
    if (self.get_score(self.head) < self.get_score(candidate_block) and
            not self.switch_reverts_finalized_block(self.head, candidate_block)):
        self.set_head(candidate_block)

def get_score(self, prestate, block):
    casper = tester.ABIContract(casper_abi, block)
    return casper.last_justified_epoch() * 10**40 + self.get_pow_difficulty(block)

def switch_reverts_finalized_block(self, old_head, new_head):
    while old_head.number > new_head.number:
        if b'finalized:'+old_head.hash in self.db:
            log.info('[WARNING] Attempt to revert failed: checkpoint {} is finalized'.format(encode_hex(old_head.hash)))
            return True
        old_head = self.get_parent(old_head)
    while new_head.number > old_head.number:
        new_head = self.get_parent(new_head)
    while new_head.hash != old_head.hash:
        if b'finalized:'+old_head.hash in self.db:
            log.info('[WARNING] Attempt to revert failed; checkpoint {} is finalized'.format(encode_hex(old_head.hash)))
            return True
        old_head = self.get_parent(old_head)
        new_head = self.get_parent(new_head)
    return False
```

## Epoch initialization
At the beginning of each new epoch, the function `initialize_epoch(epoch)` must be called. This function _utilizes no gas_ and is called automatically by the `NULL_SENDER`. The code as [implemented in Pyethereum](https://github.com/karlfloersch/pyethereum/blob/develop/ethereum/hybrid_casper/consensus.py#L20-L26) as follows:
```python
# Initalize the next epoch in the Casper contract
if state.block_number % state.config['EPOCH_LENGTH'] == 0 and state.block_number != 0:
    key, account = state.config['SENDER'], privtoaddr(state.config['SENDER'])
    data = casper_utils.casper_translator.encode('initialize_epoch', [state.block_number // state.config['EPOCH_LENGTH']])
    transaction = transactions.Transaction(state.get_nonce(account), 0, 3141592,
                                           state.config['CASPER_ADDRESS'], 0, data).sign(key)
    apply_casper_no_gas_transaction(state, transaction)
```

## Casper Vote Gas Refunds
Casper votes do not pay gas if successful, and should be considered invalid transactions and not be included in the block if failed. This avoids a large gas burden on validators. The code as [implemented in Pyethereum](https://github.com/karlfloersch/pyethereum/blob/a66ab671e0bb19327bb8cd11d69664146451c250/ethereum/messages.py#L184-L256) is as follows:
```python
def apply_transaction(state, tx):
    casper_contract = tx.to == state.env.config['CASPER_ADDRESS']
    vote = tx.data[0:4] == b'\xe9\xdc\x06\x14';
    null_sender = tx.sender == b'\xff' * 20
    if casper_contract and vote and null_sender:
        log_tx.debug('Applying CASPER no gas transaction: {}'.format(tx))
        return apply_casper_no_gas_transaction(state, tx)
    else:
        log_tx.debug('Applying transaction (non-CASPER VOTE): {}'.format(tx))
        return apply_regular_transaction(state, tx)
    ...
```
Where `_apply_casper_no_gas_transaction(state, tx)` refunds the sender&#39;s gas when the transaction is successful, and is invalid when transaction fails.

## Casper Block Ordering
A new block validity rule is added which asserts that all Casper `vote` transactions are included **after** normal transactions in a block. This allows Casper transactions to be processed in parallel with normal transactions.

This is [implemented in Pyethereum](https://github.com/karlfloersch/pyethereum/blob/develop/ethereum/common.py#L122-L133) as follows:
```python
# Validate that casper transactions come last
def validate_casper_vote_transaction_ordering(state, block):
    reached_casper_vote_transactions = False
    for tx in block.transactions:
        casper_contract = tx.to == state.env.config['CASPER_ADDRESS']
        vote = tx.data[0:4] == b'\xe9\xdc\x06\x14';
        null_sender = tx.sender == b'\xff' * 20
        if casper_contract and vote and null_sender:
            reached_casper_vote_transactions = True
        elif reached_casper_vote_transactions:
            raise InvalidTransaction('Please put all Casper transactions last')
    return True
```

## Simple Validator Voting Logic
Once a validator is logged in, they can use the following logic to determine when to send a vote:
1. When a new block is received &amp; replaces our chain&#39;s current head, call `validate(block)`
2. Inside `validate(block)` check:
    1) The block is at least `EPOCH_LENGTH/4` blocks deep to ensure that the checkpoint hash is safe to vote on.
    2) [NO_DBL_VOTE] The block&#39;s epoch has not been voted on before.
    3) [NO_SURROUND] The block&#39;s `target_epoch` &gt;= `self.latest_target_epoch` and `source_epoch` &gt;= `self.latest_source_epoch`. NOTE: This check is very simple, but it excludes a couple cases where it would be safe to vote.
3. If all of the checks pass, generate &amp; send a new vote!

NOTE: To check if a validator is logged in, one can use:
``` python
return casper.validators__start_dynasty(validator_index) >= casper.dynasty()
```

#### [[See the current validator implementation for more information.]](https://github.com/karlfloersch/pyethapp/blob/dev_env/pyethapp/validator_service.py)
