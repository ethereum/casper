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
        uint total_deposits_at_logout; //: wei_value,
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
        //return extract32(raw_call(self.validators[validator_index].addr, concat(msg_hash, sig), gas=self.VALIDATION_GAS_LIMIT, outsize=32), 0) == convert(1, 'bytes32')
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

    struct VoteMessage {
        bytes32 msg_hash;
        uint256 validator_index;
        uint256 target_epoch;
        uint256 source_epoch;
        bytes sig;
    }

    function decodeSlashableRLP(bytes vote_msg) internal returns (VoteMessage memory) {
        bytes32 msg_hash = 0x00;
        uint res = 0;
        uint inputSize = vote_msg.length + 32;
        address addr = MSG_HASHER;
        uint256 vgaslimit = MSG_HASHER_GAS_LIMIT;

        //        extract32(
        //    raw_call(self.MSG_HASHER, vote_msg_1, gas = self.MSG_HASHER_GAS_LIMIT, outsize = 32),
        //    0
        //    )
        assembly {
            let freep := mload(0x40)
            mstore(0x40, add(freep, 32))
            res := call(vgaslimit, addr, 0, vote_msg, inputSize, freep, 32)
            msg_hash := mload(freep)
        }

        require(res == 1, "vote_msg HASHER call failed.");
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
        VoteMessage memory vm1 = decodeSlashableRLP(vote_msg_1);
        // Message 2: Extract parameters
        VoteMessage memory vm2 = decodeSlashableRLP(vote_msg_2);

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

}
