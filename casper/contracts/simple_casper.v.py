#
# List of events the contract logs
# Withdrawal address used always in _from and _to as it's unique
# and validator index is removed after some events
#
Deposit: event({_from: indexed(address), _validator_index: indexed(uint256), _validation_address: address, _start_dyn: uint256, _amount: wei_value})
Vote: event({_from: indexed(address), _validator_index: indexed(uint256), _target_hash: indexed(bytes32), _target_epoch: uint256, _source_epoch: uint256})
Logout: event({_from: indexed(address), _validator_index: indexed(uint256), _end_dyn: uint256})
Withdraw: event({_to: indexed(address), _validator_index: indexed(uint256), _amount: wei_value})
Slash: event({_from: indexed(address), _offender: indexed(address), _offender_index: indexed(uint256), _bounty: wei_value})
Epoch: event({_number: indexed(uint256), _checkpoint_hash: indexed(bytes32), _is_justified: bool, _is_finalized: bool})

units: {
    sf: "scale_factor"
}

validators: public({
    # Used to determine the amount of wei the validator holds. To get the actual
    # amount of wei, multiply this by the deposit_scale_factor.
    deposit: decimal(wei/sf),
    start_dynasty: uint256,
    end_dynasty: uint256,
    is_slashed: bool,
    total_deposits_at_logout: wei_value,
    # The address which the validator's signatures must verify against
    addr: address,
    withdrawal_addr: address
}[uint256])

# Map of epoch number to checkpoint hash
checkpoint_hashes: public(bytes32[uint256])

# Next available validator index
next_validator_index: public(uint256)

# Mapping of validator's withdrawal address to their index number
validator_indexes: public(uint256[address])

# Current dynasty, it measures the number of finalized checkpoints
# in the chain from root to the parent of current block
dynasty: public(uint256)

# Map of the change to total deposits for specific dynasty
dynasty_wei_delta: public(decimal(wei / sf)[uint256])

# Total scaled deposits in the current dynasty
total_curdyn_deposits: decimal(wei / sf)

# Total scaled deposits in the previous dynasty
total_prevdyn_deposits: decimal(wei / sf)

# Mapping of dynasty to start epoch of that dynasty
dynasty_start_epoch: public(uint256[uint256])

# Mapping of epoch to what dynasty it is
dynasty_in_epoch: public(uint256[uint256])

checkpoints: public({
    # track size of scaled deposits for use in client fork choice
    cur_dyn_deposits: wei_value,
    prev_dyn_deposits: wei_value,
    # track total votes for each dynasty
    cur_dyn_votes: decimal(wei / sf)[uint256],
    prev_dyn_votes: decimal(wei / sf)[uint256],
    # Bitmap of which validator IDs have already voted
    vote_bitmap: uint256[uint256],
    # Is a vote referencing the given epoch justified?
    is_justified: bool,
    # Is a vote referencing the given epoch finalized?
    is_finalized: bool
}[uint256])  # index: target epoch

# Is the current expected hash justified
main_hash_justified: public(bool)

# Value used to calculate the per-epoch fee that validators should be charged
deposit_scale_factor: public(decimal(sf)[uint256])

last_nonvoter_rescale: public(decimal)
last_voter_rescale: public(decimal)

current_epoch: public(uint256)
last_finalized_epoch: public(uint256)
last_justified_epoch: public(uint256)

# Reward for voting as fraction of deposit size
reward_factor: public(decimal)

# Expected source epoch for a vote
expected_source_epoch: public(uint256)

# Running total of deposits slashed
total_slashed: public(wei_value[uint256])

# Flag that only allows contract initialization to happen once
initialized: bool

# ***** Parameters *****

# Length of an epoch in blocks
EPOCH_LENGTH: public(uint256)

# Length of warm up period in blocks
WARM_UP_PERIOD: public(uint256)

# Withdrawal delay in blocks
WITHDRAWAL_DELAY: public(uint256)

# Logout delay in dynasties
DYNASTY_LOGOUT_DELAY: public(uint256)

# MSG_HASHER calculator library address
# Hashes message contents but not the signature
MSG_HASHER: address

# Purity checker library address
PURITY_CHECKER: address

NULL_SENDER: public(address)
BASE_INTEREST_FACTOR: public(decimal)
BASE_PENALTY_FACTOR: public(decimal)
MIN_DEPOSIT_SIZE: public(wei_value)
START_EPOCH: public(uint256)

# ****** Pre-defined Constants ******

DEFAULT_END_DYNASTY: uint256
MSG_HASHER_GAS_LIMIT: uint256
VALIDATION_GAS_LIMIT: uint256
SLASH_FRACTION_MULTIPLIER: uint256

ONE_WEI_UINT256: wei_value
ONE_WEI_DECIMAL: decimal(wei)



@public
def init(epoch_length: uint256,
         warm_up_period: uint256,
         withdrawal_delay: uint256,
         dynasty_logout_delay: uint256,
         msg_hasher: address,
         purity_checker: address,
         null_sender: address,
         base_interest_factor: decimal,
         base_penalty_factor: decimal,
         min_deposit_size: wei_value):

    assert not self.initialized
    assert epoch_length > 0 and epoch_length < 256
    assert dynasty_logout_delay >= 2
    assert base_interest_factor >= 0.0
    assert base_penalty_factor >= 0.0
    assert min_deposit_size > 0

    self.initialized = True

    self.EPOCH_LENGTH = epoch_length
    self.WARM_UP_PERIOD = warm_up_period
    self.WITHDRAWAL_DELAY = withdrawal_delay
    self.DYNASTY_LOGOUT_DELAY = dynasty_logout_delay
    self.BASE_INTEREST_FACTOR = base_interest_factor
    self.BASE_PENALTY_FACTOR = base_penalty_factor
    self.MIN_DEPOSIT_SIZE = min_deposit_size

    self.START_EPOCH = (block.number + warm_up_period) / self.EPOCH_LENGTH

    # helper contracts
    self.MSG_HASHER = msg_hasher
    self.PURITY_CHECKER = purity_checker

    self.NULL_SENDER = null_sender

    # Start validator index counter at 1 because validator_indexes[] requires non-zero values
    self.next_validator_index = 1

    self.dynasty = 0
    self.current_epoch = self.START_EPOCH
    # TODO: test deposit_scale_factor when deploying when current_epoch > 0
    self.deposit_scale_factor[self.current_epoch] = 10000000000.0
    self.total_curdyn_deposits = 0
    self.total_prevdyn_deposits = 0
    self.DEFAULT_END_DYNASTY = 1000000000000000000000000000000
    self.MSG_HASHER_GAS_LIMIT = 200000
    self.VALIDATION_GAS_LIMIT = 200000
    self.SLASH_FRACTION_MULTIPLIER = 3
    self.ONE_WEI_UINT256 = 1
    self.ONE_WEI_DECIMAL = 1.0


# ****** Private Constants *****

# Returns number of epochs since finalization.
@private
@constant
def esf() -> uint256:
    return self.current_epoch - self.last_finalized_epoch


# Compute square root factor
@private
@constant
def sqrt_of_total_deposits() -> decimal:
    epoch: uint256 = self.current_epoch
    one_ether_as_wei: decimal = convert(convert(as_wei_value(1, "ether"), "int128"), "decimal")
    ether_deposited_as_number: decimal = convert(
        1 + as_unitless_number(
            floor(
                max(self.total_prevdyn_deposits, self.total_curdyn_deposits) *
                self.deposit_scale_factor[epoch - 1] /
                one_ether_as_wei
            )
        ),
        "decimal"
    )
    sqrt: decimal = ether_deposited_as_number / 2.0
    for i in range(20):
        sqrt = (sqrt + (ether_deposited_as_number / sqrt)) / 2.0
    return sqrt


@private
@constant
def deposit_exists() -> bool:
    return self.total_curdyn_deposits > 0.0 and self.total_prevdyn_deposits > 0.0


@private
@constant
def in_dynasty(validator_index:uint256, _dynasty:uint256) -> bool:
    start_dynasty: uint256 = self.validators[validator_index].start_dynasty
    end_dynasty: uint256 = self.validators[validator_index].end_dynasty
    return (start_dynasty <= _dynasty) and (_dynasty < end_dynasty)


# ***** Private *****

# Increment dynasty when checkpoint is finalized.
# TODO: Might want to split out the cases separately.
@private
def increment_dynasty():
    epoch: uint256 = self.current_epoch
    # Increment the dynasty if finalized
    if self.checkpoints[epoch - 2].is_finalized:
        self.dynasty += 1
        self.total_prevdyn_deposits = self.total_curdyn_deposits
        self.total_curdyn_deposits += self.dynasty_wei_delta[self.dynasty]
        self.dynasty_start_epoch[self.dynasty] = epoch
    self.dynasty_in_epoch[epoch] = self.dynasty
    if self.main_hash_justified:
        self.expected_source_epoch = epoch - 1
    self.main_hash_justified = False


@private
def insta_finalize():
    epoch: uint256 = self.current_epoch
    self.main_hash_justified = True
    self.checkpoints[epoch - 1].is_justified = True
    self.checkpoints[epoch - 1].is_finalized = True
    self.last_justified_epoch = epoch - 1
    self.last_finalized_epoch = epoch - 1
    # Log previous Epoch status update
    log.Epoch(epoch - 1, self.checkpoint_hashes[epoch - 1], True, True)


# Returns the current collective reward factor, which rewards the dynasty for high-voting levels.
@private
def collective_reward() -> decimal:
    epoch: uint256 = self.current_epoch
    live: bool = self.esf() <= 2
    if not self.deposit_exists() or not live:
        return 0.0
    # Fraction that voted
    cur_vote_frac: decimal = self.checkpoints[epoch - 1].cur_dyn_votes[self.expected_source_epoch] / self.total_curdyn_deposits
    prev_vote_frac: decimal = self.checkpoints[epoch - 1].prev_dyn_votes[self.expected_source_epoch] / self.total_prevdyn_deposits
    vote_frac: decimal = min(cur_vote_frac, prev_vote_frac)
    return vote_frac * self.reward_factor / 2.0


# Reward the given validator & miner, and reflect this in total deposit figured
@private
def proc_reward(validator_index: uint256, reward: decimal(wei/sf)):
    # Reward validator
    self.validators[validator_index].deposit += reward
    start_dynasty: uint256 = self.validators[validator_index].start_dynasty
    end_dynasty: uint256 = self.validators[validator_index].end_dynasty
    current_dynasty: uint256 = self.dynasty
    past_dynasty: uint256 = current_dynasty - 1
    if ((start_dynasty <= current_dynasty) and (current_dynasty < end_dynasty)):
        self.total_curdyn_deposits += reward
    if ((start_dynasty <= past_dynasty) and (past_dynasty < end_dynasty)):
        self.total_prevdyn_deposits += reward
    if end_dynasty < self.DEFAULT_END_DYNASTY:  # validator has submit `logout`
        self.dynasty_wei_delta[end_dynasty] -= reward
    # Reward miner
    miner_reward: wei_value = convert(
        floor(reward * self.deposit_scale_factor[self.current_epoch] / 8.0),
        "uint256"
    ) * self.ONE_WEI_UINT256
    send(block.coinbase, miner_reward)


# Removes a validator from the validator pool
@private
def delete_validator(validator_index: uint256):
    self.validator_indexes[self.validators[validator_index].withdrawal_addr] = 0
    self.validators[validator_index] = {
        deposit: 0,
        start_dynasty: 0,
        end_dynasty: 0,
        is_slashed: False,
        total_deposits_at_logout: 0,
        addr: None,
        withdrawal_addr: None
    }


# cannot be labeled @constant because of external call
# even though the call is to a pure contract call
@private
def validate_signature(msg_hash: bytes32, sig: bytes[1024], validator_index: uint256) -> bool:
    return extract32(raw_call(self.validators[validator_index].addr, concat(msg_hash, sig), gas=self.VALIDATION_GAS_LIMIT, outsize=32), 0) == convert(1, 'bytes32')


# ***** Public Constants *****

@public
@constant
def main_hash_voted_frac() -> decimal:
    return min(self.checkpoints[self.current_epoch].cur_dyn_votes[self.expected_source_epoch] / self.total_curdyn_deposits,
               self.checkpoints[self.current_epoch].prev_dyn_votes[self.expected_source_epoch] / self.total_prevdyn_deposits)


@public
@constant
def deposit_size(validator_index: uint256) -> wei_value:
    return self.ONE_WEI_UINT256 * convert(
        floor(self.validators[validator_index].deposit * self.deposit_scale_factor[self.current_epoch]),
        "uint256"
    )


@public
@constant
def total_curdyn_deposits_in_wei() -> wei_value:
    return self.ONE_WEI_UINT256 * convert(
        floor(self.total_curdyn_deposits * self.deposit_scale_factor[self.current_epoch]),
        "uint256"
    )


@public
@constant
def total_prevdyn_deposits_in_wei() -> wei_value:
    return self.ONE_WEI_UINT256 * convert(
        floor(self.total_prevdyn_deposits * self.deposit_scale_factor[self.current_epoch]),
        "uint256"
    )


@public
# cannot be labeled @constant because of external call
def validate_vote_signature(vote_msg: bytes[1024]) -> bool:
    msg_hash: bytes32 = extract32(
        raw_call(self.MSG_HASHER, vote_msg, gas=self.MSG_HASHER_GAS_LIMIT, outsize=32),
        0
    )
    # Extract parameters
    values = RLPList(vote_msg, [uint256, bytes32, uint256, uint256, bytes])
    validator_index: uint256 = values[0]
    sig: bytes[1024] = values[4]

    return self.validate_signature(msg_hash, sig, validator_index)


@public
# cannot be labeled @constant because of external call
# even though the call is to a pure contract call
def slashable(vote_msg_1: bytes[1024], vote_msg_2: bytes[1024]) -> bool:
    # Message 1: Extract parameters
    msg_hash_1: bytes32 = extract32(
        raw_call(self.MSG_HASHER, vote_msg_1, gas=self.MSG_HASHER_GAS_LIMIT, outsize=32),
        0
    )
    values_1 = RLPList(vote_msg_1, [uint256, bytes32, uint256, uint256, bytes])
    validator_index_1: uint256 = values_1[0]
    target_epoch_1: uint256 = values_1[2]
    source_epoch_1: uint256 = values_1[3]
    sig_1: bytes[1024] = values_1[4]

    # Message 2: Extract parameters
    msg_hash_2: bytes32 = extract32(
        raw_call(self.MSG_HASHER, vote_msg_2, gas=self.MSG_HASHER_GAS_LIMIT, outsize=32),
        0
    )
    values_2 = RLPList(vote_msg_2, [uint256, bytes32, uint256, uint256, bytes])
    validator_index_2: uint256 = values_2[0]
    target_epoch_2: uint256 = values_2[2]
    source_epoch_2: uint256 = values_2[3]
    sig_2: bytes[1024] = values_2[4]

    if not self.validate_signature(msg_hash_1, sig_1, validator_index_1):
        return False
    if not self.validate_signature(msg_hash_2, sig_2, validator_index_2):
        return False
    if validator_index_1 != validator_index_2:
        return False
    if self.validators[validator_index_1].start_dynasty > self.dynasty:
        return False
    if msg_hash_1 == msg_hash_2:
        return False
    if self.validators[validator_index_1].is_slashed:
        return False

    double_vote: bool = target_epoch_1 == target_epoch_2
    surround_vote: bool = (
        target_epoch_1 > target_epoch_2 and source_epoch_1 < source_epoch_2 or
        target_epoch_2 > target_epoch_1 and source_epoch_2 < source_epoch_1
    )

    return double_vote or surround_vote


#
# Helper functions that clients can call to know what to vote
#

@public
@constant
def recommended_source_epoch() -> uint256:
    return self.expected_source_epoch


@public
@constant
def recommended_target_hash() -> bytes32:
    return blockhash(self.current_epoch*self.EPOCH_LENGTH - 1)


#
# Helper methods for client fork choice
# NOTE: both methods use a non-conventional loop structure
#       with an incredibly high range and a return/break to exit.
#       This is to bypass vyper's prevention of unbounded loops.
#       This has been assessed as a reasonable tradeoff because these
#       methods are 'constant' and are only to be called locally rather
#       than as a part of an actual block tx.
#

@public
@constant
def highest_justified_epoch(min_total_deposits: wei_value) -> uint256:
    epoch: uint256
    for i in range(1000000000000000000000000000000):
        epoch = self.current_epoch - convert(i, "uint256")
        is_justified: bool = self.checkpoints[epoch].is_justified
        enough_cur_dyn_deposits: bool = self.checkpoints[epoch].cur_dyn_deposits >= min_total_deposits
        enough_prev_dyn_deposits: bool = self.checkpoints[epoch].prev_dyn_deposits >= min_total_deposits

        if is_justified and (enough_cur_dyn_deposits and enough_prev_dyn_deposits):
            return epoch

        if epoch == self.START_EPOCH:
            break

    # no justified epochs found, use 0 as default
    # to 0 out the affect of casper on fork choice
    return 0


@public
@constant
def highest_finalized_epoch(min_total_deposits: wei_value) -> int128:
    epoch: uint256
    for i in range(1000000000000000000000000000000):
        epoch = self.current_epoch - convert(i, "uint256")
        is_finalized: bool = self.checkpoints[epoch].is_finalized
        enough_cur_dyn_deposits: bool = self.checkpoints[epoch].cur_dyn_deposits >= min_total_deposits
        enough_prev_dyn_deposits: bool = self.checkpoints[epoch].prev_dyn_deposits >= min_total_deposits

        if is_finalized and (enough_cur_dyn_deposits and enough_prev_dyn_deposits):
            return convert(epoch, "int128")

        if epoch == self.START_EPOCH:
            break

    # no finalized epochs found, use -1 as default
    # to signal not to locally finalize anything
    return -1


@private
@constant
def _votable(validator_index: uint256,
             target_hash: bytes32,
             target_epoch: uint256,
             source_epoch: uint256) -> bool:
    # Check that this vote has not yet been made
    already_voted: uint256 = bitwise_and(
        self.checkpoints[target_epoch].vote_bitmap[validator_index / 256],
        shift(convert(1, 'uint256'), convert(validator_index % 256, "int128"))
    )
    if already_voted:
        return False
    # Check that the vote's target epoch and hash are correct
    if target_hash != self.recommended_target_hash():
        return False
    if target_epoch != self.current_epoch:
        return False
    # Check that the vote source points to a justified epoch
    if not self.checkpoints[source_epoch].is_justified:
        return False

    # ensure validator can vote for the target_epoch
    in_current_dynasty: bool = self.in_dynasty(validator_index, self.dynasty)
    in_prev_dynasty: bool = self.in_dynasty(validator_index, self.dynasty - 1)
    return in_current_dynasty or in_prev_dynasty


@public
@constant
def votable(vote_msg: bytes[1024]) -> bool:
    # Extract parameters
    values = RLPList(vote_msg, [uint256, bytes32, uint256, uint256, bytes])
    validator_index: uint256 = values[0]
    target_hash: bytes32 = values[1]
    target_epoch: uint256 = values[2]
    source_epoch: uint256 = values[3]

    return self._votable(validator_index, target_hash, target_epoch, source_epoch)


# ***** Public *****

# Called at the start of any epoch
@public
def initialize_epoch(epoch: uint256):
    # Check that the epoch actually has started
    computed_current_epoch: uint256 = block.number / self.EPOCH_LENGTH
    assert epoch <= computed_current_epoch and epoch == self.current_epoch + 1

    # must track the deposits related to the checkpoint _before_ updating current_epoch
    self.checkpoints[epoch].cur_dyn_deposits = self.total_curdyn_deposits_in_wei()
    self.checkpoints[epoch].prev_dyn_deposits = self.total_prevdyn_deposits_in_wei()

    self.current_epoch = epoch

    self.last_voter_rescale = 1.0 + self.collective_reward()
    self.last_nonvoter_rescale = self.last_voter_rescale / (1.0 + self.reward_factor)
    self.deposit_scale_factor[epoch] = self.deposit_scale_factor[epoch - 1] * self.last_nonvoter_rescale
    self.total_slashed[epoch] = self.total_slashed[epoch - 1]

    if self.deposit_exists():
        # Set the reward factor for the next epoch.
        adj_interest_base: decimal = self.BASE_INTEREST_FACTOR / self.sqrt_of_total_deposits()
        self.reward_factor = adj_interest_base + self.BASE_PENALTY_FACTOR * convert(convert((self.esf() - 2), "int128"), "decimal")
        # ESF is only thing that is changing and reward_factor is being used above.
        assert self.reward_factor > 0.0
    else:
        # Before the first validator deposits, new epochs are finalized instantly.
        self.insta_finalize()
        self.reward_factor = 0

    # Store checkpoint hash for easy access
    self.checkpoint_hashes[epoch] = self.recommended_target_hash()

    # Increment the dynasty if finalized
    self.increment_dynasty()

    # Log new epoch creation
    log.Epoch(epoch, self.checkpoint_hashes[epoch], False, False)


@public
@payable
def deposit(validation_addr: address, withdrawal_addr: address):
    assert extract32(raw_call(self.PURITY_CHECKER, concat('\xa1\x90\x3e\xab', convert(validation_addr, 'bytes32')), gas=500000, outsize=32), 0) != convert(0, 'bytes32')
    assert not self.validator_indexes[withdrawal_addr]
    assert msg.value >= self.MIN_DEPOSIT_SIZE
    validator_index: uint256 = self.next_validator_index
    start_dynasty: uint256 = self.dynasty + 2
    scaled_deposit: decimal(wei/sf) = self.ONE_WEI_DECIMAL * convert(convert(msg.value, "int128"), "decimal") / self.deposit_scale_factor[self.current_epoch]
    self.validators[validator_index] = {
        deposit: scaled_deposit,
        start_dynasty: start_dynasty,
        end_dynasty: self.DEFAULT_END_DYNASTY,
        is_slashed: False,
        total_deposits_at_logout: 0,
        addr: validation_addr,
        withdrawal_addr: withdrawal_addr
    }
    self.validator_indexes[withdrawal_addr] = validator_index
    self.next_validator_index += 1
    self.dynasty_wei_delta[start_dynasty] += scaled_deposit
    # Log deposit event
    log.Deposit(
        withdrawal_addr,
        validator_index,
        validation_addr,
        start_dynasty,
        msg.value
    )


@public
def logout(logout_msg: bytes[1024]):
    assert self.current_epoch == block.number / self.EPOCH_LENGTH

    # Get hash for signature, and implicitly assert that it is an RLP list
    # consisting solely of RLP elements
    msg_hash: bytes32 = extract32(
        raw_call(self.MSG_HASHER, logout_msg, gas=self.MSG_HASHER_GAS_LIMIT, outsize=32),
        0
    )
    values = RLPList(logout_msg, [uint256, uint256, bytes])
    validator_index: uint256 = values[0]
    epoch: uint256 = values[1]
    sig: bytes[1024] = values[2]

    assert self.current_epoch >= epoch
    from_withdrawal: bool = msg.sender == self.validators[validator_index].withdrawal_addr
    assert from_withdrawal or self.validate_signature(msg_hash, sig, validator_index)

    # Check that we haven't already withdrawn
    end_dynasty: uint256 = self.dynasty + self.DYNASTY_LOGOUT_DELAY
    assert self.validators[validator_index].end_dynasty > end_dynasty

    self.validators[validator_index].end_dynasty = end_dynasty
    self.validators[validator_index].total_deposits_at_logout = self.total_curdyn_deposits_in_wei()
    self.dynasty_wei_delta[end_dynasty] -= self.validators[validator_index].deposit

    log.Logout(
        self.validators[validator_index].withdrawal_addr,
        validator_index,
        self.validators[validator_index].end_dynasty
    )


# Withdraw deposited ether
@public
def withdraw(validator_index: uint256):
    # Check that we can withdraw
    end_dynasty: uint256 = self.validators[validator_index].end_dynasty
    assert self.dynasty > end_dynasty

    end_epoch: uint256 = self.dynasty_start_epoch[end_dynasty + 1]
    withdrawal_epoch: uint256 = end_epoch + self.WITHDRAWAL_DELAY
    assert self.current_epoch >= withdrawal_epoch

    # Withdraw
    withdraw_amount: wei_value
    if not self.validators[validator_index].is_slashed:
        withdraw_amount = self.ONE_WEI_UINT256 * convert(
            floor(
                self.validators[validator_index].deposit * self.deposit_scale_factor[end_epoch]
            ),
            "uint256"
        )
    else:
        # prevent a negative lookup in total_slashed
        base_epoch: uint256
        if 2 * self.WITHDRAWAL_DELAY > withdrawal_epoch:
            base_epoch = 0
        else:
            base_epoch = withdrawal_epoch - 2 * self.WITHDRAWAL_DELAY

        recently_slashed: wei_value = self.total_slashed[withdrawal_epoch] - self.total_slashed[base_epoch]
        fraction_to_slash: decimal = convert(convert(recently_slashed * self.SLASH_FRACTION_MULTIPLIER, "int128"), "decimal") / \
                                     convert(convert(self.validators[validator_index].total_deposits_at_logout, "int128"), "decimal")

        # can't withdraw a negative amount
        fraction_to_withdraw: decimal = max((1.0 - fraction_to_slash), 0.0)

        deposit_size: wei_value = self.ONE_WEI_UINT256 * convert(
            floor(self.validators[validator_index].deposit * self.deposit_scale_factor[withdrawal_epoch]),
            "uint256"
        )
        withdraw_amount = self.ONE_WEI_UINT256 * convert(
            floor(
                convert(convert(deposit_size, "int128"), "decimal") * fraction_to_withdraw
            ),
            "uint256"
        )

    send(self.validators[validator_index].withdrawal_addr, withdraw_amount)

    # Log withdraw event
    log.Withdraw(
        self.validators[validator_index].withdrawal_addr,
        validator_index,
        withdraw_amount
    )

    self.delete_validator(validator_index)


# Process a vote message
@public
def vote(vote_msg: bytes[1024]):
    assert msg.sender == self.NULL_SENDER

    # Extract parameters
    values = RLPList(vote_msg, [uint256, bytes32, uint256, uint256, bytes])
    validator_index: uint256 = values[0]
    target_hash: bytes32 = values[1]
    target_epoch: uint256 = values[2]
    source_epoch: uint256 = values[3]
    sig: bytes[1024] = values[4]

    assert self._votable(validator_index, target_hash, target_epoch, source_epoch)
    assert self.validate_vote_signature(vote_msg)

    # Record that the validator voted for this target epoch so they can't again
    self.checkpoints[target_epoch].vote_bitmap[validator_index / 256] = \
        bitwise_or(self.checkpoints[target_epoch].vote_bitmap[validator_index / 256],
                   shift(convert(1, 'uint256'), convert(validator_index % 256, "int128")))

    # Record that this vote took place
    in_current_dynasty: bool = self.in_dynasty(validator_index, self.dynasty)
    in_prev_dynasty: bool = self.in_dynasty(validator_index, self.dynasty - 1)
    current_dynasty_votes: decimal(wei/sf) = self.checkpoints[target_epoch].cur_dyn_votes[source_epoch]
    previous_dynasty_votes: decimal(wei/sf) = self.checkpoints[target_epoch].prev_dyn_votes[source_epoch]

    if in_current_dynasty:
        current_dynasty_votes += self.validators[validator_index].deposit
        self.checkpoints[target_epoch].cur_dyn_votes[source_epoch] = current_dynasty_votes
    if in_prev_dynasty:
        previous_dynasty_votes += self.validators[validator_index].deposit
        self.checkpoints[target_epoch].prev_dyn_votes[source_epoch] = previous_dynasty_votes

    # Process rewards.
    # Pay the reward if the vote was submitted in time and the vote is voting the correct data
    if self.expected_source_epoch == source_epoch:
        reward: decimal(wei/sf) = self.validators[validator_index].deposit * self.reward_factor
        self.proc_reward(validator_index, reward)

    # If enough votes with the same source_epoch and hash are made,
    # then the hash value is justified
    two_thirds_curdyn: bool = current_dynasty_votes >= self.total_curdyn_deposits * 2.0 / 3.0
    two_thirds_prevdyn: bool = previous_dynasty_votes >= self.total_prevdyn_deposits * 2.0 / 3.0
    enough_votes: bool = two_thirds_curdyn and two_thirds_prevdyn

    if enough_votes and not self.checkpoints[target_epoch].is_justified:
        self.checkpoints[target_epoch].is_justified = True
        self.last_justified_epoch = target_epoch
        self.main_hash_justified = True

        # Log target epoch status update
        log.Epoch(target_epoch, self.checkpoint_hashes[target_epoch], True, False)

        # If two epochs are justified consecutively,
        # then the source_epoch finalized
        if target_epoch == source_epoch + 1:
            self.checkpoints[source_epoch].is_finalized = True
            self.last_finalized_epoch = source_epoch
            # Log source epoch status update
            log.Epoch(source_epoch, self.checkpoint_hashes[source_epoch], True, True)

    # Log vote event
    log.Vote(
        self.validators[validator_index].withdrawal_addr,
        validator_index,
        target_hash,
        target_epoch,
        source_epoch
    )


# Cannot sign two votes for same target_epoch; no surround vote.
@public
def slash(vote_msg_1: bytes[1024], vote_msg_2: bytes[1024]):
    assert self.slashable(vote_msg_1, vote_msg_2)

    # Extract validator_index
    # `slashable` guarantees that validator_index is the same for each vote_msg
    # so just extract validator_index from vote_msg_1
    values = RLPList(vote_msg_1, [uint256, bytes32, uint256, uint256, bytes])
    validator_index: uint256 = values[0]

    # Slash the offending validator, and give a 4% "finder's fee"
    validator_deposit: wei_value = self.deposit_size(validator_index)
    slashing_bounty: wei_value = validator_deposit / 25
    self.total_slashed[self.current_epoch] += validator_deposit
    self.validators[validator_index].is_slashed = True

    # Log slashing
    log.Slash(
        msg.sender,
        self.validators[validator_index].withdrawal_addr,
        validator_index,
        slashing_bounty,
    )

    # if validator not logged out yet, remove total from next dynasty
    # and forcibly logout next dynasty
    end_dynasty: uint256 = self.validators[validator_index].end_dynasty
    if self.dynasty < end_dynasty:
        deposit: decimal(wei/sf) = self.validators[validator_index].deposit
        self.dynasty_wei_delta[self.dynasty + 1] -= deposit
        self.validators[validator_index].end_dynasty = self.dynasty + 1

        # if validator was already staged for logout at end_dynasty,
        # ensure that we don't doubly remove from total
        if end_dynasty < self.DEFAULT_END_DYNASTY:
            self.dynasty_wei_delta[end_dynasty] += deposit
        # if no previously logged out, remember the total deposits at logout
        else:
            self.validators[validator_index].total_deposits_at_logout = self.total_curdyn_deposits_in_wei()

    send(msg.sender, slashing_bounty)
