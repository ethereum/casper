pragma solidity ^0.4.23;
pragma experimental ABIEncoderV2;
import "./Decimal.sol";


contract SimpleCasper {
    using Decimal for Decimal.Data;

    event Deposit(address indexed _from,
        uint128 _validator_index,
        address _validation_address,
        uint128 _start_dyn,
        uint128 _amount);
    event Vote(address indexed _from,
        uint128 indexed _validator_index,
        bytes32 indexed _target_hash,
        uint128 _target_epoch,
        uint128 _source_epoch);
    event Logout(address indexed _from,
        uint128 indexed _validator_index,
        uint128 _end_dyn);
    event Withdraw(address indexed _to,
        uint128 indexed _validator_index,
        uint128 _amount);
    event Slash(address indexed _from,
        address indexed _offender,
        uint128 indexed _offender_index,
        uint128 _bounty);
    event Epoch(uint128 indexed _number,
        bytes32 indexed _checkpoint_hash,
        bool _is_justified,
        bool _is_finalized);

    struct Validator {
        // Used to determine the amount of wei the validator holds. To get the actual
        // amount of wei, multiply this by the deposit_scale_factor.
        Decimal.Data deposit; // : decimal(wei/m),
        uint128 start_dynasty;
        uint128 end_dynasty;
        bool is_slashed;
        uint total_deposits_at_logout; //: wei_value,
        // The address which the validator's signatures must verify against
        address addr;
        address withdrawal_addr;
    }

    Validator[] public validators;

    // Map of epoch number to checkpoint hash
    mapping(uint128 => bytes32) public checkpoint_hashes;

    // Next available validator index
    uint128 public next_validator_index;

    // Mapping of validator's withdrawal address to their index number
    address[] public validator_indexes;

    // Current dynasty, it measures the number of finalized checkpoints
    // in the chain from root to the parent of current block
    uint128 public dynasty;

    // Map of the change to total deposits for specific dynasty public(decimal(wei / m)[int128])
    Decimal.Data[] public dynasty_wei_delta;

    // Total scaled deposits in the current dynasty decimal(wei / m)
    Decimal.Data total_curdyn_deposits;

    // Total scaled deposits in the previous dynasty : decimal(wei / m)
    Decimal.Data total_prevdyn_deposits;

    // Mapping of dynasty to start epoch of that dynasty : public(int128[int128])
    uint128[] public dynasty_start_epoch;

    // Mapping of epoch to what dynasty it is : public(int128[int128])
    uint128[] public dynasty_in_epoch;

    struct Checkpoint {
        // track size of scaled deposits for use in client fork choice
        uint cur_dyn_deposits; // : wei_value,
        uint prev_dyn_deposits; // : wei_value,
        // track total votes for each dynasty
        Decimal.Data[] cur_dyn_votes; // : decimal(wei / m)[int128],
        Decimal.Data[] prev_dyn_votes; // : decimal(wei / m)[int128],
        // Bitmap of which validator IDs have already voted
        uint[] vote_bitmap; // : uint128[int128],
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

    uint128 public current_epoch; //: public(int128)
    uint128 public last_finalized_epoch; //: public(int128)
    uint128 public last_justified_epoch; //: public(int128)

    // Reward for voting as fraction of deposit size
    Decimal.Data public reward_factor; //: public(decimal)

    // Expected source epoch for a vote
    uint128 public expected_source_epoch; //: public(int128)

    // Running total of deposits slashed
    uint[] public total_slashed; //: public(wei_value[int128])

    // Flag that only allows contract initialization to happen once
    bool initialized; //: bool

    // ***** Parameters *****

    // Length of an epoch in blocks
    uint128 public EPOCH_LENGTH; //: public(int128)

    // Length of warm up period in blocks
    uint128 public WARM_UP_PERIOD; //: public(int128)

    // Withdrawal delay in blocks
    uint128 public WITHDRAWAL_DELAY; //: public(int128)

    // Logout delay in dynasties
    uint128 public DYNASTY_LOGOUT_DELAY; //: public(int128)

    // MSG_HASHER calculator library address
    // Hashes message contents but not the signature
    address MSG_HASHER; //: address

    // Purity checker library address
    address PURITY_CHECKER; //: address

    Decimal.Data public BASE_INTEREST_FACTOR; //: public(decimal)
    Decimal.Data public BASE_PENALTY_FACTOR; //: public(decimal)
    uint public MIN_DEPOSIT_SIZE; //: public(wei_value)
    uint128 public START_EPOCH; //: public(int128)
    uint128 DEFAULT_END_DYNASTY; //: int128
    uint128 MSG_HASHER_GAS_LIMIT; //: int128
    uint128 VALIDATION_GAS_LIMIT; //: int128
    uint128 SLASH_FRACTION_MULTIPLIER; //: int128


    constructor() public {

    }

    // @public
    function init(
        uint128 epoch_length,
        uint128 warm_up_period,
        uint128 withdrawal_delay,
        uint128 dynasty_logout_delay,
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

        START_EPOCH = uint128((block.number + warm_up_period) / EPOCH_LENGTH);

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

    // ****** Private Constants *****
    function max(Decimal.Data a, Decimal.Data b) private pure returns (Decimal.Data) {
        return a.comp(b) > 0 ? a : b;
    }

    // Returns number of epochs since finalization.
    function esf() private constant returns (uint128){
        return current_epoch - last_finalized_epoch;
    }

    // Compute square root factor
    function sqrt_of_total_deposits() private constant returns (Decimal.Data) {
        uint128 epoch = current_epoch;
        Decimal.Data memory ether_deposited_as_number_decimal = max(total_prevdyn_deposits, total_curdyn_deposits);
        ether_deposited_as_number_decimal = ether_deposited_as_number_decimal.mul(deposit_scale_factor[epoch - 1]);
        ether_deposited_as_number_decimal = ether_deposited_as_number_decimal.div(Decimal.fromUint(1 ether));
        uint128 ether_deposited_as_number = uint128(ether_deposited_as_number_decimal.toUint()) + 1;
        Decimal.Data memory sqrt = Decimal.Data({
            num: ether_deposited_as_number,
            den: 2
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
        uint128 epoch = current_epoch;
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

    function insta_finalize() private {
        uint128 epoch = current_epoch;
        main_hash_justified = true;
        checkpoints[epoch - 1].is_justified = true;
        checkpoints[epoch - 1].is_finalized = true;
        last_justified_epoch = epoch - 1;
        last_finalized_epoch = epoch - 1;
        // Log previous Epoch status update
        emit Epoch(epoch - 1, checkpoint_hashes[epoch - 1], true, true);
    }

}
