pragma solidity ^0.4.24;
pragma experimental ABIEncoderV2;

import "./Decimal.sol";
import "./RLP.sol";


contract SimpleCasper {
    using Decimal for Decimal.Data;
    using RLP for bytes;
    using RLP for RLP.RLPItem;
    using RLP for RLP.Iterator;

    event Deposit(address indexed _from,
        uint256 _validator_index,
        address _validation_address,
        uint256 _start_dyn,
        uint256 _amount);
    event Vote(address indexed _from,
        uint256 indexed _validator_index,
        bytes32 indexed _target_hash,
        uint256 _target_epoch,
        uint256 _source_epoch);
    event Logout(address indexed _from,
        uint256 indexed _validator_index,
        uint256 _end_dyn);
    event Withdraw(address indexed _to,
        uint256 indexed _validator_index,
        uint256 _amount);
    event Slash(address indexed _from,
        address indexed _offender,
        uint256 indexed _offender_index,
        uint256 _bounty);
    event Epoch(uint256 indexed _number,
        bytes32 indexed _checkpoint_hash,
        bool _is_justified,
        bool _is_finalized);

    struct Validator {
        // Used to determine the amount of wei the validator holds. To get the actual
        // amount of wei, multiply this by the deposit_scale_factor.
        Decimal.Data deposit; // : decimal(wei/m),
        uint256 start_dynasty;
        uint256 end_dynasty;
        bool is_slashed;
        uint256 total_deposits_at_logout; //: wei_value,
        // The address which the validator's signatures must verify against
        address addr;
        address withdrawal_addr;
    }

    Validator[] public validators;

    // Map of epoch number to checkpoint hash
    mapping(uint256 => bytes32) public checkpoint_hashes;

    // Next available validator index
    uint256 public next_validator_index;

    // Mapping of validator's withdrawal address to their index number
    address[] public validator_indexes;

    // Current dynasty, it measures the number of finalized checkpoints
    // in the chain from root to the parent of current block
    uint256 public dynasty;

    // Map of the change to total deposits for specific dynasty public(decimal(wei / m)[int128])
    Decimal.Data[] public dynasty_wei_delta;

    // Total scaled deposits in the current dynasty decimal(wei / m)
    Decimal.Data total_curdyn_deposits;

    // Total scaled deposits in the previous dynasty : decimal(wei / m)
    Decimal.Data total_prevdyn_deposits;

    // Mapping of dynasty to start epoch of that dynasty : public(int128[int128])
    uint256[] public dynasty_start_epoch;

    // Mapping of epoch to what dynasty it is : public(int128[int128])
    uint256[] public dynasty_in_epoch;

    struct Checkpoint {
        // track size of scaled deposits for use in client fork choice
        uint cur_dyn_deposits; // : wei_value,
        uint prev_dyn_deposits; // : wei_value,
        // track total votes for each dynasty
        Decimal.Data[] cur_dyn_votes; // : decimal(wei / m)[int128],
        Decimal.Data[] prev_dyn_votes; // : decimal(wei / m)[int128],
        // Bitmap of which validator IDs have already voted
        uint[] vote_bitmap; // : uint256[int128],
        // Is a vote referencing the given epoch justified?
        bool is_justified; //: bool,
        // Is a vote referencing the given epoch finalized?
        bool is_finalized; //: bool
    }

    Checkpoint[] public checkpoints; // [int128])  // index: target epoch

    // Is the current expected hash justified
    bool public main_hash_justified; //: public(bool)

    // Value used to calculate the per-epoch fee that validators should be charged
    Decimal.Data[] public deposit_scale_factor;// : public(decimal(m)[int128])

    Decimal.Data public last_nonvoter_rescale; //: public(decimal)
    Decimal.Data public last_voter_rescale; //: public(decimal)

    uint256 public current_epoch; //: public(int128)
    uint256 public last_finalized_epoch; //: public(int128)
    uint256 public last_justified_epoch; //: public(int128)

    // Reward for voting as fraction of deposit size
    Decimal.Data public reward_factor; //: public(decimal)

    // Expected source epoch for a vote
    uint256 public expected_source_epoch; //: public(int128)

    // Running total of deposits slashed
    uint[] public total_slashed; //: public(wei_value[int128])

    // Flag that only allows contract initialization to happen once
    bool initialized; //: bool

    // ***** Parameters *****

    // Length of an epoch in blocks
    uint256 public EPOCH_LENGTH; //: public(int128)

    // Length of warm up period in blocks
    uint256 public WARM_UP_PERIOD; //: public(int128)

    // Withdrawal delay in blocks
    uint256 public WITHDRAWAL_DELAY; //: public(int128)

    // Logout delay in dynasties
    uint256 public DYNASTY_LOGOUT_DELAY; //: public(int128)

    // MSG_HASHER calculator library address
    // Hashes message contents but not the signature
    address MSG_HASHER; //: address

    // Purity checker library address
    address PURITY_CHECKER; //: address

    Decimal.Data public BASE_INTEREST_FACTOR; //: public(decimal)
    Decimal.Data public BASE_PENALTY_FACTOR; //: public(decimal)
    uint public MIN_DEPOSIT_SIZE; //: public(wei_value)
    uint256 public START_EPOCH; //: public(int128)
    uint256 DEFAULT_END_DYNASTY; //: int128
    uint256 MSG_HASHER_GAS_LIMIT; //: int128
    uint256 VALIDATION_GAS_LIMIT; //: int128
    uint256 SLASH_FRACTION_MULTIPLIER; //: int128


    constructor() public {

    }

    // @public
    function init(
        uint256 epoch_length,
        uint256 warm_up_period,
        uint256 withdrawal_delay,
        uint256 dynasty_logout_delay,
        address msg_hasher,
        address purity_checker,
        Decimal.Data base_interest_factor,
        Decimal.Data base_penalty_factor,
        uint min_deposit_size // wei_value
    ) public {

        require(!initialized);
        require(epoch_length > 0 && epoch_length < 256);
        require(warm_up_period >= 0);
        require(withdrawal_delay >= 0);
        require(dynasty_logout_delay >= 2);
        require(base_interest_factor.compZero() > 0);
        require(base_penalty_factor.compZero() > 0);
        require(min_deposit_size > 0);

        initialized = true;

        EPOCH_LENGTH = epoch_length;
        WARM_UP_PERIOD = warm_up_period;
        WITHDRAWAL_DELAY = withdrawal_delay;
        DYNASTY_LOGOUT_DELAY = dynasty_logout_delay;
        BASE_INTEREST_FACTOR = base_interest_factor;
        BASE_PENALTY_FACTOR = base_penalty_factor;
        MIN_DEPOSIT_SIZE = min_deposit_size;

        START_EPOCH = uint256((block.number + warm_up_period) / EPOCH_LENGTH);

        // helper contracts
        MSG_HASHER = msg_hasher;
        PURITY_CHECKER = purity_checker;

        // Start validator index counter at 1 because validator_indexes[] requires non-zero values
        next_validator_index = 1;

        dynasty = 0;
        current_epoch = START_EPOCH;
        // TODO: test deposit_scale_factor when deploying when current_epoch > 0
        deposit_scale_factor[current_epoch] = Decimal.fromUint(10000000000);
        total_curdyn_deposits = Decimal.fromUint(0);
        total_prevdyn_deposits = Decimal.fromUint(0);
        DEFAULT_END_DYNASTY = 1000000000000000000000000000000;
        MSG_HASHER_GAS_LIMIT = 200000;
        VALIDATION_GAS_LIMIT = 200000;
        SLASH_FRACTION_MULTIPLIER = 3;
    }

    /**
     * @dev This function is original. The Solidity not have max(a, b) of global function.
     */
    function max(Decimal.Data a, Decimal.Data b) private pure returns (Decimal.Data) {
        return a.comp(b) > 0 ? a : b;
    }

    /**
     * @dev This function is original. The Solidity not have min(a, b) of global function.
     */
    function min(Decimal.Data a, Decimal.Data b) private pure returns (Decimal.Data) {
        return a.comp(b) > 0 ? b : a;
    }

    /**
     * @dev original.
     */
    function concat(bytes32 a, bytes b) public pure returns (bytes result) {
        uint blen = 32 + b.length;
        uint blockLen = (blen / 32) * 32;
        if (blen % 32 > 0) {
            blockLen += 32;
        }
        assembly {
            let freep := mload(0x40)
            mstore(0x40, add(freep, blockLen))
            mstore(freep, blen)
            mstore(add(freep, 32), a)
            calldatacopy(add(freep, 64), 100, sub(blen, 32))
            result := freep
        }
    }

    // ****** Private Constants *****

    // Returns number of epochs since finalization.
    function esf() private constant returns (uint256){
        return current_epoch - last_finalized_epoch;
    }

    // Compute square root factor
    function sqrt_of_total_deposits() private constant returns (Decimal.Data) {
        uint256 epoch = current_epoch;
        Decimal.Data memory ether_deposited_as_number_decimal = max(total_prevdyn_deposits, total_curdyn_deposits);
        ether_deposited_as_number_decimal = ether_deposited_as_number_decimal.mul(deposit_scale_factor[epoch - 1]);
        ether_deposited_as_number_decimal = ether_deposited_as_number_decimal.div(Decimal.fromUint(1 ether));
        uint256 ether_deposited_as_number = uint256(ether_deposited_as_number_decimal.toUint()) + 1;
        Decimal.Data memory sqrt = Decimal.Data({
            num : ether_deposited_as_number,
            den : 2
            });
        for (uint i; i < 20; i++) {
            sqrt = sqrt.add(Decimal.fromUint(ether_deposited_as_number));
            sqrt = sqrt.div(sqrt);
            sqrt = sqrt.div(Decimal.fromUint(2));
        }
        return sqrt;
    }

    function deposit_exists() private constant returns (bool) {
        return total_curdyn_deposits.compZero() > 1 && total_prevdyn_deposits.compZero() > 1;
    }


    // ** ** * Private ** ** *

    // Increment dynasty when checkpoint is finalized.
    // TODO : Might want to split out the cases separately.
    function increment_dynasty() private {
        uint256 epoch = current_epoch;
        // Increment the dynasty if finalized
        if (checkpoints[epoch - 2].is_finalized) {
            dynasty += 1;
            total_prevdyn_deposits = total_curdyn_deposits;
            total_curdyn_deposits = total_curdyn_deposits.add(dynasty_wei_delta[dynasty]);
            dynasty_start_epoch[dynasty] = epoch;
        }
        dynasty_in_epoch[epoch] = dynasty;
        if (main_hash_justified) {
            expected_source_epoch = epoch - 1;
            main_hash_justified = false;
        }
    }

    // line:226
    function insta_finalize() private {
        uint256 epoch = current_epoch;
        main_hash_justified = true;
        checkpoints[epoch - 1].is_justified = true;
        checkpoints[epoch - 1].is_finalized = true;
        last_justified_epoch = epoch - 1;
        last_finalized_epoch = epoch - 1;
        // Log previous Epoch status update
        emit Epoch(epoch - 1, checkpoint_hashes[epoch - 1], true, true);
    }

    // Returns the current collective reward factor, which rewards the dynasty for high-voting levels.
    // line:239
    function collective_reward() private view returns (Decimal.Data) {
        uint256 epoch = current_epoch;
        bool live = esf() <= 2;
        if (!deposit_exists() || !live) {
            return Decimal.fromUint(0);
        }
        // Fraction that voted
        Decimal.Data memory cur_vote_frac = checkpoints[epoch - 1].cur_dyn_votes[expected_source_epoch].div(total_curdyn_deposits);
        Decimal.Data memory prev_vote_frac = checkpoints[epoch - 1].prev_dyn_votes[expected_source_epoch].div(total_prevdyn_deposits);
        Decimal.Data memory vote_frac = min(cur_vote_frac, prev_vote_frac);
        return vote_frac.mul(reward_factor).div(Decimal.fromUint(2));
    }

    // Reward the given validator & miner, and reflect this in total deposit figured
    // line:253
    function proc_reward(uint256 validator_index, uint256 reward) private {
        // Reward validator
        validators[validator_index].deposit = validators[validator_index].deposit.add(Decimal.fromUint(reward));
        uint256 start_dynasty = validators[validator_index].start_dynasty;
        uint256 end_dynasty = validators[validator_index].end_dynasty;
        uint256 current_dynasty = dynasty;
        uint256 past_dynasty = current_dynasty - 1;
        if ((start_dynasty <= current_dynasty) && (current_dynasty < end_dynasty)) {
            total_curdyn_deposits = total_curdyn_deposits.add(Decimal.fromUint(reward));
        }
        if ((start_dynasty <= past_dynasty) && (past_dynasty < end_dynasty)) {
            total_prevdyn_deposits = total_prevdyn_deposits.add(Decimal.fromUint(reward));
        }
        if (end_dynasty < DEFAULT_END_DYNASTY) {// validator has submit `logout`
            dynasty_wei_delta[end_dynasty] = dynasty_wei_delta[end_dynasty].sub(Decimal.fromUint(reward));
        }
        // Reward miner
        Decimal.Data memory reward_decimal = Decimal.fromUint(reward);
        reward_decimal = reward_decimal.mul(deposit_scale_factor[current_epoch]).div(Decimal.fromUint(8));
        block.coinbase.transfer(reward_decimal.toUint());
    }

    // Removes a validator from the validator pool
    // line:272
    function delete_validator(uint256 validator_index) private {
        validator_indexes[uint(validators[validator_index].withdrawal_addr)] = 0x00;
        validators[validator_index] = Validator({
            deposit : Decimal.fromUint(0),
            start_dynasty : 0,
            end_dynasty : 0,
            is_slashed : false,
            total_deposits_at_logout : 0,
            addr : 0x00,
            withdrawal_addr : 0x00
            });
    }

    // cannot be labeled @constant because of external call
    // even though the call is to a pure contract call
    // line:288
    function validate_signature(bytes32 msg_hash, bytes sig, uint256 validator_index) private returns (bool) {
        address addr = validators[validator_index].addr;
        uint256 vgaslimit = VALIDATION_GAS_LIMIT;
        bytes memory input = SimpleCasper(this).concat(msg_hash, sig);
        uint inputSize = input.length + 32;
        bytes32 result = 0x00;
        uint res = 0;
        assembly {
            res := call(vgaslimit, addr, 0, input, inputSize, result, 32)
        }
        //return extract32(raw_call(validators[validator_index].addr, concat(msg_hash, sig), gas=VALIDATION_GAS_LIMIT, outsize=32), 0) == convert(1, 'bytes32')
        return res == 1 && result == bytes32(1);
    }

    // ***** Public Constants *****

    // line:296
    function main_hash_voted_frac() public constant returns (Decimal.Data) {
        Decimal.Data memory cur_dyn_vote = checkpoints[current_epoch].cur_dyn_votes[expected_source_epoch];
        cur_dyn_vote = cur_dyn_vote.div(total_curdyn_deposits);
        Decimal.Data memory prev_dyn_vote = checkpoints[current_epoch].prev_dyn_votes[expected_source_epoch];
        prev_dyn_vote = prev_dyn_vote.div(total_prevdyn_deposits);
        return min(cur_dyn_vote, prev_dyn_vote);
    }
    // line:303
    function deposit_size(uint256 validator_index) public constant returns (uint256) {
        return validators[validator_index].deposit.mul(deposit_scale_factor[current_epoch]).toUint();
    }

    // line:309
    function total_curdyn_deposits_in_wei() public constant returns (uint256) {
        return total_curdyn_deposits.mul(deposit_scale_factor[current_epoch]).toUint();
    }

    // line:315
    function total_prevdyn_deposits_in_wei() public constant returns (uint256) {
        return total_prevdyn_deposits.mul(deposit_scale_factor[current_epoch]).toUint();
    }

    // original struct. Resolve over stack size.
    struct VoteMessage {
        bytes32 msg_hash;
        uint256 validator_index;
        bytes32 target_hash;
        uint256 target_epoch;
        uint256 source_epoch;
        bytes sig;
    }

    // original function. Resolve duplicate of MSG_HASHER raw_call.
    function getMsgHash(bytes message) internal returns (bytes32 msg_hash) {
        uint res = 0;
        uint inputSize = message.length + 32;
        address addr = MSG_HASHER;
        uint256 vgaslimit = MSG_HASHER_GAS_LIMIT;
        assembly {
            let freep := mload(0x40)
            mstore(0x40, add(freep, 32))
            res := call(vgaslimit, addr, 0, message, inputSize, freep, 32)
            msg_hash := mload(freep)
        }

        require(res == 1, "HASHER call failed.");
    }

    function decodeVoteMessageRLP(bytes vote_msg) internal returns (VoteMessage memory) {
        bytes32 msg_hash = 0x00;

        //        extract32(
        //    raw_call(MSG_HASHER, vote_msg_1, gas = MSG_HASHER_GAS_LIMIT, outsize = 32),
        //    0
        //    )
        msg_hash = getMsgHash(vote_msg);

        //    values_1 = RLPList(vote_msg_1, [int128, bytes32, int128, int128, bytes])
        RLP.Iterator memory values = vote_msg.toRLPItem().iterator();
        VoteMessage memory decode;
        decode.msg_hash = msg_hash;
        decode.validator_index = values.next().toUint();
        values.next();
        decode.target_epoch = values.next().toUint();
        decode.source_epoch = values.next().toUint();
        decode.sig = values.next().toBytes();
        return decode;
    }

    // cannot be labeled @constant because of external call
    // even though the call is to a pure contract call
    //line:322
    function slashable(bytes vote_msg_1, bytes vote_msg_2) public returns (bool) {
        // Message 1: Extract parameters
        //    values_1 = RLPList(vote_msg_1, [int128, bytes32, int128, int128, bytes])
        VoteMessage memory vm1 = decodeVoteMessageRLP(vote_msg_1);
        // Message 2: Extract parameters
        VoteMessage memory vm2 = decodeVoteMessageRLP(vote_msg_2);

        if (!validate_signature(vm1.msg_hash, vm1.sig, vm1.validator_index)) {
            return false;
        }
        if (!validate_signature(vm2.msg_hash, vm2.sig, vm2.validator_index)) {
            return false;
        }
        if (vm1.validator_index != vm2.validator_index) {
            return false;
        }
        if (vm1.msg_hash == vm2.msg_hash) {
            return false;
        }
        if (validators[vm1.validator_index].is_slashed) {
            return false;
        }

        bool double_vote = vm1.target_epoch == vm2.target_epoch;
        bool surround_vote = (
        vm1.target_epoch > vm2.target_epoch && vm1.source_epoch < vm2.source_epoch ||
        vm2.target_epoch > vm1.target_epoch && vm2.source_epoch < vm1.source_epoch
        );

        return double_vote || surround_vote;
    }

    //
    // Helper functions that clients can call to know what to vote
    //
    // line:371
    function recommended_source_epoch() public constant returns (uint256) {
        return expected_source_epoch;
    }

    // line:377
    function recommended_target_hash() public constant returns (bytes32) {
        return blockhash(current_epoch * EPOCH_LENGTH - 1);
    }

    //
    // Helper methods for client fork choice
    // NOTE: both methods use a non-conventional loop structure
    //       with an incredibly high range and a return/break to exit.
    //       This is to bypass vyper's prevention of unbounded loops.
    //       This has been assessed as a reasonable tradeoff because these
    //       methods are 'constant' and are only to be called locally rather
    //       than as a part of an actual block tx.
    //
    // line:393
    function highest_justified_epoch(uint256 min_total_deposits) public constant returns (uint256) {
        uint256 epoch = 0;
        for (uint i; i < 1000000000000000000000000000000; i++) {
            epoch = current_epoch - i;
            bool is_justified = checkpoints[epoch].is_justified;
            bool enough_cur_dyn_deposits = checkpoints[epoch].cur_dyn_deposits >= min_total_deposits;
            bool enough_prev_dyn_deposits = checkpoints[epoch].prev_dyn_deposits >= min_total_deposits;

            if (is_justified && (enough_cur_dyn_deposits && enough_prev_dyn_deposits)) {
                return epoch;
            }
            if (epoch == START_EPOCH) {
                break;
            }
        }
        // no justified epochs found, use 0 as default
        // to 0 out the affect of casper on fork choice
        return 0;
    }

    // line:413
    function highest_finalized_epoch(uint256 min_total_deposits) public constant returns (uint256) {
        uint256 epoch = 0;
        for (uint i = 0; i < 1000000000000000000000000000000; i++) {
            epoch = current_epoch - i;
            bool is_finalized = checkpoints[epoch].is_finalized;
            bool enough_cur_dyn_deposits = checkpoints[epoch].cur_dyn_deposits >= min_total_deposits;
            bool enough_prev_dyn_deposits = checkpoints[epoch].prev_dyn_deposits >= min_total_deposits;

            if (is_finalized && (enough_cur_dyn_deposits && enough_prev_dyn_deposits)) {
                return epoch;
            }
            if (epoch == START_EPOCH) {
                break;
            }
        }
        // no finalized epochs found, use -1 as default
        // to signal not to locally finalize anything
        return uint256(- 1);
    }

    // ***** Public *****

    // Called at the start of any epoch
    // line:435
    function initialize_epoch(uint256 epoch) public {
        // Check that the epoch actually has started
        uint256 computed_current_epoch = uint256(block.number / EPOCH_LENGTH);
        require(epoch <= computed_current_epoch && epoch == current_epoch + 1);

        // must track the deposits related to the checkpoint _before_ updating current_epoch
        checkpoints[epoch].cur_dyn_deposits = total_curdyn_deposits_in_wei();
        checkpoints[epoch].prev_dyn_deposits = total_prevdyn_deposits_in_wei();

        current_epoch = epoch;

        last_voter_rescale = Decimal.fromUint(1).add(collective_reward());
        last_nonvoter_rescale = last_voter_rescale.div(Decimal.fromUint(1).add(reward_factor));
        deposit_scale_factor[epoch] = deposit_scale_factor[epoch - 1].mul(last_nonvoter_rescale);
        total_slashed[epoch] = total_slashed[epoch - 1];

        if (deposit_exists()) {
            // Set the reward factor for the next epoch.
            Decimal.Data memory adj_interest_base = BASE_INTEREST_FACTOR.div(sqrt_of_total_deposits());
            Decimal.Data memory tmp = BASE_PENALTY_FACTOR.mul(Decimal.fromUint(esf() - 2));
            reward_factor = adj_interest_base.add(tmp);
            // ESF is only thing that is changing and reward_factor is being used above.
            require(reward_factor.compZero() > 0);
        } else {
            // Before the first validator deposits, new epochs are finalized instantly.
            insta_finalize();
            reward_factor = Decimal.fromUint(0);
        }

        // Store checkpoint hash for easy access
        checkpoint_hashes[epoch] = recommended_target_hash();

        // Increment the dynasty if finalized
        increment_dynasty();

        // Log new epoch creation
        emit Epoch(epoch, checkpoint_hashes[epoch], false, false);
    }

    // line:474
    function deposit(address validation_addr, address withdrawal_addr) public payable {
        //assert extract32(raw_call(PURITY_CHECKER, concat('\xa1\x90\x3e\xab', convert(validation_addr, 'bytes32')), gas=500000, outsize=32), 0) != convert(0, 'bytes32')
        require(PURITY_CHECKER.call.gas(500000)(bytes4(keccak256("submit(address)")), bytes32(validation_addr)));
        require(validator_indexes[uint256(withdrawal_addr)] != 0x00);
        require(msg.value >= MIN_DEPOSIT_SIZE);
        uint256 validator_index = next_validator_index;
        uint256 start_dynasty = dynasty + 2;
        Decimal.Data memory scaled_deposit = Decimal.fromUint(msg.value).div(deposit_scale_factor[current_epoch]);
        validators[validator_index] = Validator({
            deposit : scaled_deposit,
            start_dynasty : start_dynasty,
            end_dynasty : DEFAULT_END_DYNASTY,
            is_slashed : false,
            total_deposits_at_logout : 0,
            addr : validation_addr,
            withdrawal_addr : withdrawal_addr
            });
        validator_indexes[uint256(withdrawal_addr)] = address(validator_index);
        next_validator_index += 1;
        dynasty_wei_delta[start_dynasty] = dynasty_wei_delta[start_dynasty].add(scaled_deposit);
        // Log deposit event
        emit Deposit(
            withdrawal_addr,
            validator_index,
            validation_addr,
            start_dynasty,
            msg.value
        );
    }

    // line:504
    function logout(bytes logout_msg) public {
        require(current_epoch == uint256(block.number / EPOCH_LENGTH));

        // Get hash for signature, and implicitly assert that it is an RLP list
        // consisting solely of RLP elements
        //extract32(
        //raw_call(MSG_HASHER, logout_msg, gas = MSG_HASHER_GAS_LIMIT, outsize = 32),
        //0
        //)
        bytes32 msg_hash = getMsgHash(logout_msg);
        RLP.Iterator memory values = logout_msg.toRLPItem().iterator();
        //values = RLPList(logout_msg, [int128, int128, bytes])
        uint256 validator_index = values.next().toUint();
        uint256 epoch = values.next().toUint();
        bytes memory sig = values.next().toBytes();

        require(current_epoch >= epoch);
        bool from_withdrawal = msg.sender == validators[validator_index].withdrawal_addr;
        require(from_withdrawal || validate_signature(msg_hash, sig, validator_index));

        // Check that we haven't already withdrawn
        uint256 end_dynasty = dynasty + DYNASTY_LOGOUT_DELAY;
        require(validators[validator_index].end_dynasty > end_dynasty);

        validators[validator_index].end_dynasty = end_dynasty;
        validators[validator_index].total_deposits_at_logout = total_curdyn_deposits_in_wei();
        dynasty_wei_delta[end_dynasty] = dynasty_wei_delta[end_dynasty].sub(validators[validator_index].deposit);

        emit Logout(
            validators[validator_index].withdrawal_addr,
            validator_index,
            validators[validator_index].end_dynasty
        );
    }

    // Withdraw deposited ether
    // line: 539
    function withdraw(uint256 validator_index) public {
        // Check that we can withdraw
        uint256 end_dynasty = validators[validator_index].end_dynasty;
        require(dynasty > end_dynasty);

        uint256 end_epoch = dynasty_start_epoch[end_dynasty + 1];
        uint256 withdrawal_epoch = end_epoch + WITHDRAWAL_DELAY;
        require(current_epoch >= withdrawal_epoch);

        // Withdraw
        uint256 withdraw_amount = 0;
        if (!validators[validator_index].is_slashed) {
            withdraw_amount = validators[validator_index].deposit.mul(deposit_scale_factor[end_epoch]).toUint();
        } else {
            uint256 recently_slashed = total_slashed[withdrawal_epoch] - total_slashed[withdrawal_epoch - 2 * WITHDRAWAL_DELAY];
            Decimal.Data memory fraction_to_slash = Decimal.Data({
                num : recently_slashed * SLASH_FRACTION_MULTIPLIER,
                den : validators[validator_index].total_deposits_at_logout
                });

            // can't withdraw a negative amount
            Decimal.Data memory fraction_to_withdraw = max((Decimal.fromUint(1).sub(fraction_to_slash)), Decimal.fromUint(0));

            Decimal.Data memory deposit_size_decimal = validators[validator_index].deposit.mul(deposit_scale_factor[withdrawal_epoch]);
            withdraw_amount = deposit_size_decimal.mul(fraction_to_withdraw).toUint();
        }
        validators[validator_index].withdrawal_addr.transfer(withdraw_amount);

        // Log withdraw event
        emit Withdraw(
            validators[validator_index].withdrawal_addr,
            validator_index,
            withdraw_amount
        );

        delete_validator(validator_index);
    }

    // vyper shift translate function.
    function shift(uint256 src, int128 _shift) internal pure returns (uint256) {
        if (_shift >= 0) {
            return src << _shift;
        } else {
            return src >> (_shift * - 1);
        }
    }

    // Process a vote message
    // line:576
    function vote(bytes vote_msg) public {
        // Get hash for signature, and implicitly assert that it is an RLP list
        // consisting solely of RLP elements
        VoteMessage memory vm = decodeVoteMessageRLP(vote_msg);

        require(validate_signature(vm.msg_hash, vm.sig, vm.validator_index));
        // Check that this vote has not yet been made
        require((checkpoints[vm.target_epoch].vote_bitmap[uint256(vm.validator_index / 256)] &
        shift(uint256(1), int128(vm.validator_index % 256))) != 0);
        // Check that the vote's target epoch and hash are correct
        require(vm.target_hash == recommended_target_hash());
        require(vm.target_epoch == current_epoch);
        // Check that the vote source points to a justified epoch
        require(checkpoints[vm.source_epoch].is_justified);

        // ensure validator can vote for the target_epoch
        uint256 start_dynasty = validators[vm.validator_index].start_dynasty;
        uint256 end_dynasty = validators[vm.validator_index].end_dynasty;
        uint256 current_dynasty = dynasty;
        uint256 past_dynasty = current_dynasty - 1;
        bool in_current_dynasty = ((start_dynasty <= current_dynasty) && (current_dynasty < end_dynasty));
        bool in_prev_dynasty = ((start_dynasty <= past_dynasty) && (past_dynasty < end_dynasty));
        require(in_current_dynasty || in_prev_dynasty);

        // Record that the validator voted for this target epoch so they can't again
        checkpoints[vm.target_epoch].vote_bitmap[uint256(vm.validator_index / 256)] =
        (checkpoints[vm.target_epoch].vote_bitmap[uint256(vm.validator_index / 256)] |
        shift(uint256(1), int128(vm.validator_index % 256)));

        // Record that this vote took place
        Decimal.Data memory current_dynasty_votes = checkpoints[vm.target_epoch].cur_dyn_votes[vm.source_epoch];
        Decimal.Data memory previous_dynasty_votes = checkpoints[vm.target_epoch].prev_dyn_votes[vm.source_epoch];
        if (in_current_dynasty) {
            current_dynasty_votes = current_dynasty_votes.add(validators[vm.validator_index].deposit);
            checkpoints[vm.target_epoch].cur_dyn_votes[vm.source_epoch] = current_dynasty_votes;
        }
        if (in_prev_dynasty) {
            previous_dynasty_votes = previous_dynasty_votes.add(validators[vm.validator_index].deposit);
            checkpoints[vm.target_epoch].prev_dyn_votes[vm.source_epoch] = previous_dynasty_votes;
        }
        // Process rewards.
        // Pay the reward if the vote was submitted in time and the vote is voting the correct data
        if (expected_source_epoch == vm.source_epoch) {
            uint256 reward = validators[vm.validator_index].deposit.mul(reward_factor).toUint();
            proc_reward(vm.validator_index, reward);
        }

        // If enough votes with the same vm.source_epoch and hash are made,
        // then the hash value is justified
        if ((current_dynasty_votes.comp(total_curdyn_deposits.mul(Decimal.fromUint(2)).div(Decimal.fromUint(3))) > 0
        && previous_dynasty_votes.comp(total_prevdyn_deposits.mul(Decimal.fromUint(2)).div(Decimal.fromUint(3))) > 0)
            && !checkpoints[vm.target_epoch].is_justified) {
            checkpoints[vm.target_epoch].is_justified = true;
            last_justified_epoch = vm.target_epoch;
            main_hash_justified = true;
        }

        // Log target epoch status update
        emit Epoch(vm.target_epoch, checkpoint_hashes[vm.target_epoch], true, false);

        // If two epochs are justified consecutively,
        // then the vm.source_epoch finalized
        if (vm.target_epoch == vm.source_epoch + 1) {
            checkpoints[vm.source_epoch].is_finalized = true;
            last_finalized_epoch = vm.source_epoch;
            // Log source epoch status update
            emit Epoch(vm.source_epoch, checkpoint_hashes[vm.source_epoch], true, true);
        }

        // Log vote event
        emit Vote(
            validators[vm.validator_index].withdrawal_addr,
            vm.validator_index,
            vm.target_hash,
            vm.target_epoch,
            vm.source_epoch
        );
    }

    // Cannot sign two votes for same target_epoch; no surround vote.
    // line:663
    function slash(bytes vote_msg_1, bytes vote_msg_2) public {
        require(slashable(vote_msg_1, vote_msg_2));

        // Extract validator_index
        // `slashable` guarantees that validator_index is the same for each vote_msg
        // so just extract validator_index from vote_msg_1
        RLP.Iterator memory values = vote_msg_1.toRLPItem().iterator();
        uint256 validator_index = values.next().toUint();

        // Slash the offending validator, and give a 4% "finder's fee"
        uint256 validator_deposit = deposit_size(validator_index);
        uint256 slashing_bounty = uint256(validator_deposit / 25);
        total_slashed[current_epoch] += validator_deposit;
        validators[validator_index].is_slashed = true;

        // Log slashing
        emit Slash(
            msg.sender,
            validators[validator_index].withdrawal_addr,
            validator_index,
            slashing_bounty
        );

        // if validator not logged out yet, remove total from next dynasty
        // and forcibly logout next dynasty
        uint256 end_dynasty = validators[validator_index].end_dynasty;
        if (dynasty < end_dynasty) {
            Decimal.Data memory deposit_decimal = validators[validator_index].deposit;
            dynasty_wei_delta[dynasty + 1] = dynasty_wei_delta[dynasty + 1].sub(deposit_decimal);
            validators[validator_index].end_dynasty = dynasty + 1;

            // if validator was already staged for logout at end_dynasty,
            // ensure that we don't doubly remove from total
            if (end_dynasty < DEFAULT_END_DYNASTY) {
                dynasty_wei_delta[end_dynasty] = dynasty_wei_delta[end_dynasty].add(deposit_decimal);
                // if no previously logged out, remember the total deposits at logout
            } else {
                validators[validator_index].total_deposits_at_logout = total_curdyn_deposits_in_wei();
            }
        }
        msg.sender.transfer(slashing_bounty);
    }
}
