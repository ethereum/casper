# Information about validators
validators: public({
    # Used to determine the amount of wei the validator holds. To get the actual
    # amount of wei, multiply this by the deposit_scale_factor.
    deposit: decimal(wei/m),
    # The dynasty the validator is joining
    start_dynasty: num,
    # The dynasty the validator is leaving
    end_dynasty: num,
    # The address which the validator's signatures must verify to (to be later replaced with validation code)
    addr: address,
    # Addess to withdraw to
    withdrawal_addr: address
}[num])

# Historical checkoint hashes
checkpoint_hashes: public(bytes32[num])

# Number of validators
nextValidatorIndex: public(num)

# Mapping of validator's signature address to their index number
validator_indexes: public(num[address])

# The current dynasty (validator set changes between dynasties)
dynasty: public(num)

# Amount of wei added to the total deposits in the next dynasty
next_dynasty_wei_delta: public(decimal(wei / m))

# Amount of wei added to the total deposits in the dynasty after that
second_next_dynasty_wei_delta: public(decimal(wei / m))

# Total deposits in the current dynasty
total_curdyn_deposits: decimal(wei / m)

# Total deposits in the previous dynasty
total_prevdyn_deposits: decimal(wei / m)

# Mapping of dynasty to start epoch of that dynasty
dynasty_start_epoch: public(num[num])

# Mapping of epoch to what dynasty it is
dynasty_in_epoch: public(num[num])

# Information for use in processing cryptoeconomic commitments
votes: public({
    # How many votes are there for this source epoch from the current dynasty
    cur_dyn_votes: decimal(wei / m)[num],
    # From the previous dynasty
    prev_dyn_votes: decimal(wei / m)[num],
    # Bitmap of which validator IDs have already voted
    vote_bitmap: num256[num][bytes32],
    # Is a vote referencing the given epoch justified?
    is_justified: bool,
    # Is a vote referencing the given epoch finalized?
    is_finalized: bool
}[num])  # index: target epoch

# Is the current expected hash justified
main_hash_justified: public(bool)

# Value used to calculate the per-epoch fee that validators should be charged
deposit_scale_factor: public(decimal(m)[num])

# For debug purposes
# TODO: Remove this when ready.
last_nonvoter_rescale: public(decimal)
last_voter_rescale: public(decimal)

# Length of an epoch in blocks
epoch_length: public(num)

# Withdrawal delay in blocks
withdrawal_delay: public(num)

# Current epoch
current_epoch: public(num)

# Last finalized epoch
last_finalized_epoch: public(num)

# Last justified epoch
last_justified_epoch: public(num)

# Expected source epoch for a vote
expected_source_epoch: public(num)

# Can withdraw destroyed deposits
owner: address

# Total deposits destroyed
total_destroyed: wei_value

# Sighash calculator library address
sighasher: address

# Purity checker library address
purity_checker: address

# Reward for voting as fraction of deposit size
reward_factor: public(decimal)

# Base interest factor
base_interest_factor: public(decimal)

# Base penalty factor
base_penalty_factor: public(decimal)

# Log topic for vote
vote_log_topic: bytes32

# Minimum deposit size if no one else is validating
min_deposit_size: wei_value

@public
def __init__(  # Epoch length, delay in epochs for withdrawing
        _epoch_length: num, _withdrawal_delay: num,
        # Owner (backdoor), sig hash calculator, purity checker
        _owner: address, _sighasher: address, _purity_checker: address,
        # Base interest and base penalty factors
        _base_interest_factor: decimal, _base_penalty_factor: decimal,
        # Min deposit size
        _min_deposit_size: wei_value):
    # Epoch length
    self.epoch_length = _epoch_length
    # Delay in epochs for withdrawing
    self.withdrawal_delay = _withdrawal_delay
    # Start validator index counter at 1 because validator_indexes[] requires non-zero values
    self.nextValidatorIndex = 1
    # Temporary backdoor for testing purposes (to allow recovering destroyed deposits)
    self.owner = _owner
    # Set deposit scale factor
    self.deposit_scale_factor[0] = 10000000000.0
    # Start dynasty counter at 0
    self.dynasty = 0
    # Initialize the epoch counter
    self.current_epoch = block.number / self.epoch_length
    # Set the sighash calculator address
    self.sighasher = _sighasher
    # Set the purity checker address
    self.purity_checker = _purity_checker
    # self.votes[0].committed = True
    # Set initial total deposit counter
    self.total_curdyn_deposits = 0
    self.total_prevdyn_deposits = 0
    # Constants that affect interest rates and penalties
    self.base_interest_factor = _base_interest_factor
    self.base_penalty_factor = _base_penalty_factor
    self.vote_log_topic = sha3("vote()")
    # Constants that affect the min deposit size
    self.min_deposit_size = _min_deposit_size

# ***** Constants *****
@public
@constant
def get_main_hash_voted_frac() -> decimal:
    return min(self.votes[self.current_epoch].cur_dyn_votes[self.expected_source_epoch] / self.total_curdyn_deposits,
               self.votes[self.current_epoch].prev_dyn_votes[self.expected_source_epoch] / self.total_prevdyn_deposits)

@public
@constant
def get_deposit_size(validator_index: num) -> num(wei):
    return floor(self.validators[validator_index].deposit * self.deposit_scale_factor[self.current_epoch])

@public
@constant
def get_total_curdyn_deposits() -> wei_value:
    return floor(self.total_curdyn_deposits * self.deposit_scale_factor[self.current_epoch])

@public
@constant
def get_total_prevdyn_deposits() -> wei_value:
    return floor(self.total_prevdyn_deposits * self.deposit_scale_factor[self.current_epoch])

# Helper functions that clients can call to know what to vote
@public
@constant
def get_recommended_source_epoch() -> num:
    return self.expected_source_epoch

@public
@constant
def get_recommended_target_hash() -> bytes32:
    return blockhash(self.current_epoch*self.epoch_length-1)

@private
@constant
def deposit_exists() -> bool:
    return self.total_curdyn_deposits > 0 and self.total_prevdyn_deposits > 0

# ***** Private *****

# Increment dynasty when checkpoint is finalized.
# TODO: Might want to split out the cases separately.
@private
def increment_dynasty():
    epoch = self.current_epoch
    # Increment the dynasty if finalized
    if self.votes[epoch-2].is_finalized:
        self.dynasty += 1
        self.total_prevdyn_deposits = self.total_curdyn_deposits
        self.total_curdyn_deposits += self.next_dynasty_wei_delta
        self.next_dynasty_wei_delta = self.second_next_dynasty_wei_delta
        self.second_next_dynasty_wei_delta = 0
        self.dynasty_start_epoch[self.dynasty] = epoch
    self.dynasty_in_epoch[epoch] = self.dynasty
    if self.main_hash_justified:
        self.expected_source_epoch = epoch - 1
    self.main_hash_justified = False

# Returns number of epochs since finalization.
@private
def get_esf() -> num:
    epoch = self.current_epoch
    return epoch - self.last_finalized_epoch

# Returns the current collective reward factor, which rewards the dynasty for high-voting levels.
@private
def get_collective_reward() -> decimal:
    epoch = self.current_epoch
    live = self.get_esf() <= 2
    if not self.deposit_exists() or not live:
        return 0.0
    # Fraction that voted
    cur_vote_frac = self.votes[epoch - 1].cur_dyn_votes[self.expected_source_epoch] / self.total_curdyn_deposits
    prev_vote_frac = self.votes[epoch - 1].prev_dyn_votes[self.expected_source_epoch] / self.total_prevdyn_deposits
    vote_frac = min(cur_vote_frac, prev_vote_frac)
    return vote_frac * self.reward_factor / 2

@private
def insta_finalize():
    epoch = self.current_epoch
    self.main_hash_justified = True
    self.votes[epoch - 1].is_justified = True
    self.votes[epoch - 1].is_finalized = True
    self.last_justified_epoch = epoch - 1
    self.last_finalized_epoch = epoch - 1

# Compute square root factor
@private
def get_sqrt_of_total_deposits() -> decimal:
    epoch = self.current_epoch
    ether_deposited_as_number = floor(max(self.total_prevdyn_deposits, self.total_curdyn_deposits) *
                                      self.deposit_scale_factor[epoch - 1] / as_wei_value(1, ether)) + 1
    sqrt = ether_deposited_as_number / 2.0
    for i in range(20):
        sqrt = (sqrt + (ether_deposited_as_number / sqrt)) / 2
    return sqrt

# ***** Public *****

# Called at the start of any epoch
@public
def initialize_epoch(epoch: num):
    # Check that the epoch actually has started
    computed_current_epoch = block.number / self.epoch_length
    assert epoch <= computed_current_epoch and epoch == self.current_epoch + 1

    # Setup
    self.current_epoch = epoch

    # Reward if finalized at least in the last two epochs
    self.last_nonvoter_rescale = (1 + self.get_collective_reward() - self.reward_factor)
    self.last_voter_rescale = self.last_nonvoter_rescale * (1 + self.reward_factor)
    self.deposit_scale_factor[epoch] = self.deposit_scale_factor[epoch - 1] * self.last_nonvoter_rescale

    if self.deposit_exists():
        # Set the reward factor for the next epoch.
        adj_interest_base = self.base_interest_factor / self.get_sqrt_of_total_deposits()  # TODO: sqrt is based on previous epoch starting deposit
        self.reward_factor = adj_interest_base + self.base_penalty_factor * self.get_esf()  # TODO: might not be bpf. clarify is positive?
        # ESF is only thing that is changing and reward_factor is being used above.
        assert self.reward_factor > 0
    else:
        self.insta_finalize()  # TODO: comment on why.
        self.reward_factor = 0

    # Increment the dynasty if finalized
    self.increment_dynasty()

    # Store checkpoint hash for easy access
    self.checkpoint_hashes[epoch] = self.get_recommended_target_hash()

# Send a deposit to join the validator set
@public
@payable
def deposit(validation_addr: address, withdrawal_addr: address):
    assert self.current_epoch == block.number / self.epoch_length
    assert extract32(raw_call(self.purity_checker, concat('\xa1\x90>\xab', as_bytes32(validation_addr)), gas=500000, outsize=32), 0) != as_bytes32(0)
    assert not self.validator_indexes[withdrawal_addr]
    assert msg.value >= self.min_deposit_size
    self.validators[self.nextValidatorIndex] = {
        deposit: msg.value / self.deposit_scale_factor[self.current_epoch],
        start_dynasty: self.dynasty + 2,
        end_dynasty: 1000000000000000000000000000000,
        addr: validation_addr,
        withdrawal_addr: withdrawal_addr
    }
    self.validator_indexes[withdrawal_addr] = self.nextValidatorIndex
    self.nextValidatorIndex += 1
    self.second_next_dynasty_wei_delta += msg.value / self.deposit_scale_factor[self.current_epoch]

# Log in or log out from the validator set. A logged out validator can log
# back in later, if they do not log in for an entire withdrawal period,
# they can get their money out
@public
def logout(logout_msg: bytes <= 1024):
    assert self.current_epoch == block.number / self.epoch_length
    # Get hash for signature, and implicitly assert that it is an RLP list
    # consisting solely of RLP elements
    sighash = extract32(raw_call(self.sighasher, logout_msg, gas=200000, outsize=32), 0)
    # Extract parameters
    values = RLPList(logout_msg, [num, num, bytes])
    validator_index = values[0]
    epoch = values[1]
    sig = values[2]
    assert self.current_epoch >= epoch
    # Signature check
    assert extract32(raw_call(self.validators[validator_index].addr, concat(sighash, sig), gas=500000, outsize=32), 0) == as_bytes32(1)
    # Check that we haven't already withdrawn
    assert self.validators[validator_index].end_dynasty > self.dynasty + 2
    # Set the end dynasty
    self.validators[validator_index].end_dynasty = self.dynasty + 2
    self.second_next_dynasty_wei_delta -= self.validators[validator_index].deposit

# Removes a validator from the validator pool
@private
def delete_validator(validator_index: num):
    if self.validators[validator_index].end_dynasty > self.dynasty + 2:
        self.next_dynasty_wei_delta -= self.validators[validator_index].deposit
    self.validator_indexes[self.validators[validator_index].withdrawal_addr] = 0
    self.validators[validator_index] = {
        deposit: 0,
        start_dynasty: 0,
        end_dynasty: 0,
        addr: None,
        withdrawal_addr: None
    }

# Withdraw deposited ether
@public
def withdraw(validator_index: num):
    # Check that we can withdraw
    assert self.dynasty >= self.validators[validator_index].end_dynasty + 1
    end_epoch = self.dynasty_start_epoch[self.validators[validator_index].end_dynasty + 1]
    assert self.current_epoch >= end_epoch + self.withdrawal_delay
    # Withdraw
    withdraw_amount = floor(self.validators[validator_index].deposit * self.deposit_scale_factor[end_epoch])
    send(self.validators[validator_index].withdrawal_addr, withdraw_amount)
    self.delete_validator(validator_index)

# Reward the given validator & miner, and reflect this in total deposit figured
@private
def proc_reward(validator_index: num, reward: num(wei/m)):
    start_epoch = self.dynasty_start_epoch[self.validators[validator_index].start_dynasty]
    self.validators[validator_index].deposit += reward
    start_dynasty = self.validators[validator_index].start_dynasty
    end_dynasty = self.validators[validator_index].end_dynasty
    current_dynasty = self.dynasty
    past_dynasty = current_dynasty - 1
    if ((start_dynasty <= current_dynasty) and (current_dynasty < end_dynasty)):
        self.total_curdyn_deposits += reward
    if ((start_dynasty <= past_dynasty) and (past_dynasty < end_dynasty)):
        self.total_prevdyn_deposits += reward
    if current_dynasty == end_dynasty - 1:
        self.next_dynasty_wei_delta -= reward
    if current_dynasty == end_dynasty - 2:
        self.second_next_dynasty_wei_delta -= reward
    send(block.coinbase, floor(reward * self.deposit_scale_factor[self.current_epoch] / 8))

# Process a vote message
@public
def vote(vote_msg: bytes <= 1024):
    # Get hash for signature, and implicitly assert that it is an RLP list
    # consisting solely of RLP elements
    sighash = extract32(raw_call(self.sighasher, vote_msg, gas=200000, outsize=32), 0)
    # Extract parameters
    values = RLPList(vote_msg, [num, bytes32, num, num, bytes])
    validator_index = values[0]
    target_hash = values[1]
    target_epoch = values[2]
    source_epoch = values[3]
    sig = values[4]
    # Check the signature
    assert extract32(raw_call(self.validators[validator_index].addr, concat(sighash, sig), gas=500000, outsize=32), 0) == as_bytes32(1)
    # Check that this vote has not yet been made
    assert not bitwise_and(self.votes[target_epoch].vote_bitmap[target_hash][validator_index / 256],
                           shift(as_num256(1), validator_index % 256))
    # Check that the vote's target hash is correct
    assert target_hash == self.get_recommended_target_hash()
    # Check that the vote source points to a justified epoch
    assert self.votes[source_epoch].is_justified
    # Check that we are at least (epoch length / 4) blocks into the epoch
    # assert block.number % self.epoch_length >= self.epoch_length / 4
    # Original starting dynasty of the validator; fail if before
    start_dynasty = self.validators[validator_index].start_dynasty
    # Ending dynasty of the current login period
    end_dynasty = self.validators[validator_index].end_dynasty
    # Dynasty of the vote
    current_dynasty = self.dynasty_in_epoch[target_epoch]
    past_dynasty = current_dynasty - 1
    in_current_dynasty = ((start_dynasty <= current_dynasty) and (current_dynasty < end_dynasty))
    in_prev_dynasty = ((start_dynasty <= past_dynasty) and (past_dynasty < end_dynasty))
    assert in_current_dynasty or in_prev_dynasty
    # Record that the validator voted for this target epoch so they can't again
    self.votes[target_epoch].vote_bitmap[target_hash][validator_index / 256] = \
        bitwise_or(self.votes[target_epoch].vote_bitmap[target_hash][validator_index / 256],
                   shift(as_num256(1), validator_index % 256))
    # Record that this vote took place
    current_dynasty_votes = self.votes[target_epoch].cur_dyn_votes[source_epoch]
    previous_dynasty_votes = self.votes[target_epoch].prev_dyn_votes[source_epoch]
    if in_current_dynasty:
        current_dynasty_votes += self.validators[validator_index].deposit
        self.votes[target_epoch].cur_dyn_votes[source_epoch] = current_dynasty_votes
    if in_prev_dynasty:
        previous_dynasty_votes += self.validators[validator_index].deposit
        self.votes[target_epoch].prev_dyn_votes[source_epoch] = previous_dynasty_votes
    # Process rewards.
    # Check that we have not yet voted for this target_epoch
    # Pay the reward if the vote was submitted in time and the vote is voting the correct data
    if self.current_epoch == target_epoch and self.expected_source_epoch == source_epoch:
        reward = floor(self.validators[validator_index].deposit * self.reward_factor)
        self.proc_reward(validator_index, reward)
    # If enough votes with the same source_epoch and hash are made,
    # then the hash value is justified
    if (current_dynasty_votes >= self.total_curdyn_deposits * 2 / 3 and
            previous_dynasty_votes >= self.total_prevdyn_deposits * 2 / 3) and \
            not self.votes[target_epoch].is_justified:
        self.votes[target_epoch].is_justified = True
        self.last_justified_epoch = target_epoch
        if target_epoch == self.current_epoch:
            self.main_hash_justified = True
        # If two epochs are justified consecutively,
        # then the source_epoch finalized
        if target_epoch == source_epoch + 1:
            self.votes[source_epoch].is_finalized = True
            self.last_finalized_epoch = source_epoch
    raw_log([self.vote_log_topic], vote_msg)

# Cannot make two prepares in the same epoch; no surrond vote.
@public
def slash(vote_msg_1: bytes <= 1024, vote_msg_2: bytes <= 1024):
    # Message 1: Extract parameters
    sighash_1 = extract32(raw_call(self.sighasher, vote_msg_1, gas=200000, outsize=32), 0)
    values = RLPList(vote_msg_1, [num, bytes32, num, num, bytes])
    validator_index_1 = values[0]
    target_epoch_1 = values[2]
    source_epoch_1 = values[3]
    sig_1 = values[4]
    # Check the signature for vote message 1
    assert extract32(raw_call(self.validators[validator_index_1].addr, concat(sighash_1, sig_1), gas=500000, outsize=32), 0) == as_bytes32(1)
    # Message 2: Extract parameters
    sighash_2 = extract32(raw_call(self.sighasher, vote_msg_2, gas=200000, outsize=32), 0)
    values = RLPList(vote_msg_2, [num, bytes32, num, num, bytes])
    validator_index_2 = values[0]
    target_epoch_2 = values[2]
    source_epoch_2 = values[3]
    sig_2 = values[4]
    # Check the signature for vote message 2
    assert extract32(raw_call(self.validators[validator_index_2].addr, concat(sighash_2, sig_2), gas=500000, outsize=32), 0) == as_bytes32(1)
    # Check the messages are from the same validator
    assert validator_index_1 == validator_index_2
    # Check the messages are not the same
    assert sighash_1 != sighash_2
    # Detect slashing
    slashing_condition_detected = False
    if target_epoch_1 == target_epoch_2:
        # NO DBL VOTE
        slashing_condition_detected = True
    elif (target_epoch_1 > target_epoch_2 and source_epoch_1 < source_epoch_2) or \
            (target_epoch_2 > target_epoch_1 and source_epoch_2 < source_epoch_1):
        # NO SURROUND VOTE
        slashing_condition_detected = True
    assert slashing_condition_detected
    # Delete the offending validator, and give a 4% "finder's fee"
    validator_deposit = self.get_deposit_size(validator_index_1)
    slashing_bounty = validator_deposit / 25
    self.total_destroyed += validator_deposit * 24 / 25
    self.delete_validator(validator_index_1)
    send(msg.sender, slashing_bounty)

# Temporary backdoor for testing purposes (to allow recovering destroyed deposits)
@public
def owner_withdraw():
    send(self.owner, self.total_destroyed)
    self.total_destroyed = 0

# Change backdoor address (set to zero to remove entirely)
@public
def change_owner(new_owner: address):
    if self.owner == msg.sender:
        self.owner = new_owner
