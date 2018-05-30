
## Outline

This document outlines the components of implementing an FFG Validator. These include the:
- Validator workflow overview
- Validator States
- Validator Code
- Vote format and generation
- Logout format
- `simple_casper` contract overview
- Casper transaction gas refunds
- Simple validator voting logic.

## Validator Workflow Overview
1. Create valcode:
    - Deploy a new contract which is used to validate a validator's signature.
2. Submit Deposit:
    - Call `casper.deposit(validation_addr, withdrawal_addr)` passing in the validation code contract address from step (1) and your withdrawal address.
3. **[Once each Epoch]** Submit new vote message:
    - Wait to vote until the checkpoint is at least `EPOCH_LENGTH/4` blocks deep in the main chain. This ensures all validators vote on the same block.
    - Generate unsigned vote message based on your chain's current head.
    - Broadcast the unsigned vote transaction to the network.
4. Logout:
    - Submit logout message.
    - Call `casper.logout(logout_msg)` passing in your newly generated logout message.
5. Withdraw:
    - Call `casper.withdraw(validator_index)` and your funds will be sent to your validator's withdrawal address specified in step (2).

## Validator States
Validators are highly stateful. They must handle valcode creation, depositing, voting, and logging out. Each stage also requires waiting for transaction confirmations. Because of this complexity, a mapping of state to handler is used.

The validator state mapping [implemented in pyethapp](https://github.com/karlfloersch/pyethapp/blob/47df0f592533dded868f052dd51d37ebe57e612f/pyethapp/validator_service.py#L58-L67) is as follows:
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

For basic signature verification, [ecdsa signatures are currently being used](https://github.com/karlfloersch/pyethereum/blob/a66ab671e0bb19327bb8cd11d69664146451c250/ethereum/hybrid_casper/casper_utils.py#L73). The validation code for these ecdsa signatures can be found [here](https://github.com/karlfloersch/pyethereum/blob/a66ab671e0bb19327bb8cd11d69664146451c250/ethereum/hybrid_casper/casper_utils.py#L52). Note, this LLL code uses the elliptic curve public key recovery precompile.

The validation code contract is currently being deployed as a part of the `induct_validator()` function [found here](https://github.com/karlfloersch/pyethereum/blob/a66ab671e0bb19327bb8cd11d69664146451c250/ethereum/hybrid_casper/casper_utils.py#L83-L87):
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
Casper vote messages are simply included in normal transactions sent to the Casper contract's `casper.vote(vote_msg)` function.

## Casper Vote Generation
To generate a Casper vote which votes on your chain's current head, first get the vote message contents. To do this, using the Casper contract call:
- `casper.validator_indexes(WITHDRAWAL_ADDRESS)` for the `validator_index`
- `casper.recommended_target_hash()` for the `target_hash`
- `casper.current_epoch()` for the `target_epoch`
- `casper.recommended_source_epoch()` for the `source_epoch`

Next, RLP encode all these elements. To compute your signature, compute the `sha3` hash of your vote's RLP encoded list, and sign the hash. Your signature must be valid when checked against your validator's `validation_code` contract. Finally, append your signature to the end of the vote message contents.

This is [implemented in Pyethereum](https://github.com/karlfloersch/pyethereum/blob/a66ab671e0bb19327bb8cd11d69664146451c250/ethereum/hybrid_casper/casper_utils.py#L71-L75) as follows:
```
def mk_vote(validator_index, target_hash, target_epoch, source_epoch, key):
    msg_hash = utils.sha3(rlp.encode([validator_index, target_hash, target_epoch, source_epoch]))
    v, r, s = utils.ecdsa_raw_sign(msg_hash, key)
    sig = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
    return rlp.encode([validator_index, target_hash, target_epoch, source_epoch, sig])
```

## Logout Message Generation
Like the Casper vote messages, a logout message is an RLP encoded list where the last element is the validator's signature. The elements of the unsigned list are the `validator_index` and `epoch` where epoch is the current epoch. A signature is generated in the same way it is done with votes above.

This is [implemented in Pyethereum](https://github.com/karlfloersch/pyethereum/blob/a66ab671e0bb19327bb8cd11d69664146451c250/ethereum/hybrid_casper/casper_utils.py#L77-L81) as follows:
```
def mk_logout(validator_index, epoch, key):
    msg_hash = utils.sha3(rlp.encode([validator_index, epoch]))
    v, r, s = utils.ecdsa_raw_sign(msg_hash, key)
    sig = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
    return rlp.encode([validator_index, epoch, sig])
```

## Simple Casper Contract High Level Overview
The Casper smart contract contains Casper's core logic. It is written in Vyper &amp; can be deployed to the blockchain like any other contract to `CASPER_ADDR`. Casper messages are then sent to the contract by calling `vote(vote_msg)` where `vote_msg` is a Casper vote messaged as outlined above.

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

Once a new epoch begins, this function is immediately called as the first transaction applied to the state. See Epoch initialization for more details.

#### `def deposit(validation_addr, withdrawal_addr)`
Accepts deposits from prospective validators &amp; adds them to the next validator set.

#### `def logout(logout_msg)`
Initiates validator logout. The validator must continue to validate for `dynasty_logout_delay` dynasties before entering the `withdrawal_delay` waiting period.

#### `def withdraw(validator_index)`
If the validator has waited for a period greater than `withdrawal_delay` epochs past their `end_dynasty`, then send them ETH equivalent to their deposit.

#### `def vote(vote_msg)`
Called once by each validator each epoch. The vote message contains the fields presented in Casper Vote Format.

#### `def slash(vote_msg_1, vote_msg_2)`
Can be called by anyone who detects a slashing condition violation. Sends 4% of slashed validator's funds to the caller as a finder's fee and burns the remaining 96%.

## Casper Vote Gas Refunds
Casper votes do not pay gas if successful, and will be considered invalid transactions and not be included in the block if failed. This avoids a large gas burden on validators.

## Simple Validator Voting Logic
Once a validator is logged in, they can use the following logic to determine when to send a vote:
1. When a new block is received &amp; replaces our chain's current head, call `validate(block)`
2. Inside `validate(block)` check:
    1) The block is at least `EPOCH_LENGTH/4` blocks deep to ensure that the checkpoint hash is safe to vote on.
    2) [NO_DBL_VOTE] The block's epoch has not been voted on before.
    3) [NO_SURROUND] The block's `target_epoch` &gt;= `self.latest_target_epoch` and `source_epoch` &gt;= `self.latest_source_epoch`. NOTE: This check is very simple, but it excludes a couple cases where it would be safe to vote.
3. If all of the checks pass, generate &amp; send a new vote!

NOTE: To check if a validator is logged in, one can use:
``` python
return casper.validators__start_dynasty(validator_index) <= casper.dynasty()
```

#### [[See the current validator implementation for more information.]](https://github.com/karlfloersch/pyethapp/blob/dev_env/pyethapp/validator_service.py)
