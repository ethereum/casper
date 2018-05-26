import pytest
import os
import rlp

from ethereum.abi import ContractTranslator
from ethereum.genesis_helpers import mk_basic_state
from ethereum.transactions import Transaction
from ethereum.tools import tester
from ethereum import utils
from vyper import compiler

from utils.valcodes import compile_valcode_to_evm_bytecode

OWN_DIR = os.path.dirname(os.path.realpath(__file__))

GAS_PRICE = 25 * 10**9

VYPER_RLP_DECODER_TX_HEX = "0xf9035b808506fc23ac0083045f788080b903486103305660006109ac5260006109cc527f0100000000000000000000000000000000000000000000000000000000000000600035046109ec526000610a0c5260006109005260c06109ec51101515585760f86109ec51101561006e5760bf6109ec510336141558576001610a0c52610098565b60013560f76109ec51036020035260005160f66109ec510301361415585760f66109ec5103610a0c525b61022060016064818352015b36610a0c511015156100b557610291565b7f0100000000000000000000000000000000000000000000000000000000000000610a0c5135046109ec526109cc5160206109ac51026040015260016109ac51016109ac5260806109ec51101561013b5760016109cc5161044001526001610a0c516109cc5161046001376001610a0c5101610a0c5260216109cc51016109cc52610281565b60b86109ec5110156101d15760806109ec51036109cc51610440015260806109ec51036001610a0c51016109cc51610460013760816109ec5114156101ac5760807f01000000000000000000000000000000000000000000000000000000000000006001610a0c5101350410151558575b607f6109ec5103610a0c5101610a0c5260606109ec51036109cc51016109cc52610280565b60c06109ec51101561027d576001610a0c51013560b76109ec510360200352600051610a2c526038610a2c5110157f01000000000000000000000000000000000000000000000000000000000000006001610a0c5101350402155857610a2c516109cc516104400152610a2c5160b66109ec5103610a0c51016109cc516104600137610a2c5160b66109ec5103610a0c510101610a0c526020610a2c51016109cc51016109cc5261027f565bfe5b5b5b81516001018083528114156100a4575b5050601f6109ac511115155857602060206109ac5102016109005260206109005103610a0c5261022060016064818352015b6000610a0c5112156102d45761030a565b61090051610a0c516040015101610a0c51610900516104400301526020610a0c5103610a0c5281516001018083528114156102c3575b50506109cc516109005101610420526109cc5161090051016109005161044003f35b61000461033003610004600039610004610330036000f31b2d4f"  # NOQA
MSG_HASHER_TX_HEX = "0xf9016d808506fc23ac0083026a508080b9015a6101488061000e6000396101565660007f01000000000000000000000000000000000000000000000000000000000000006000350460f8811215610038576001915061003f565b60f6810391505b508060005b368312156100c8577f01000000000000000000000000000000000000000000000000000000000000008335048391506080811215610087576001840193506100c2565b60b881121561009d57607f8103840193506100c1565b60c08112156100c05760b68103600185013560b783036020035260005101840193505b5b5b50610044565b81810360388112156100f4578060c00160005380836001378060010160002060e052602060e0f3610143565b61010081121561010557600161011b565b6201000081121561011757600261011a565b60035b5b8160005280601f038160f701815382856020378282600101018120610140526020610140f350505b505050505b6000f31b2d4f"  # NOQA
PURITY_CHECKER_TX_HEX = "0xf90405808506fc23ac00830927c08080b903f26103da56600035601c52740100000000000000000000000000000000000000006020526f7fffffffffffffffffffffffffffffff6040527fffffffffffffffffffffffffffffffff8000000000000000000000000000000060605274012a05f1fffffffffffffffffffffffffdabf41c006080527ffffffffffffffffffffffffed5fa0e000000000000000000000000000000000060a05263a1903eab600051141561038857602060046101403734156100b457600080fd5b60043560205181106100c557600080fd5b50610140513b60008114156100da57fe610367565b806000610160610140513c806060026101600160008160007fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff818352015b84845110151561012b5761036256610351565b610100601f8551036101600151068060020a7f80010000000000000000000000000000000000000030ffff1c0e000000000000161561016657fe5b607f811115816060111516156101a55780607f036101000a600186516101600101510484602002876021026101600101528451605f820301855261033d565b60f4811460f282141760f18214171561033c576000607f6001860360200288610160010151111560606001870360200289610160010151101516600286101516156101f5576002850390506102e2565b607f6003860360200288610160010151111560606003870360200289610160010151101516605a6002870360200289610160010151141660036001870360200289610160010151141660048610151615610254576004850390506102e1565b605a6001860360200288610160010151146002861015161561027b576002850390506102e0565b6090600186036020028861016001015114600286101516156102a2576002850390506102df565b609060018603602002886101600101511060806001870360200289610160010151101516600286101516156102dc576002850390506102de565bfe5b5b5b5b5b8060200287602102610160010151600060c052602060c0200154156103065761033a565b60308160200288610160010151141561031e57610339565b60608160200288610160010151141561033657610338565bfe5b5b5b505b5b808460200287610160010152600184019350505b5b8151600101808352811415610118575b505050505b50600161014051600060c052602060c0200155600160005261017c610160f3005b63c23697a860005114156103d557602060046101403734156103a957600080fd5b60043560205181106103ba57600080fd5b5061014051600060c052602060c020015460005260206000f3005b5b6100046103da036100046000396100046103da036000f31b2d4f"  # NOQA
PURITY_CHECKER_ABI = [{'name': 'check(address)', 'type': 'function', 'constant': True, 'inputs': [{'name': 'addr', 'type': 'address'}], 'outputs': [{'name': 'out', 'type': 'bool'}]}, {'name': 'submit(address)', 'type': 'function', 'constant': False, 'inputs': [{'name': 'addr', 'type': 'address'}], 'outputs': [{'name': 'out', 'type': 'bool'}]}]  # NOQA

EPOCH_LENGTH = 10
WARM_UP_PERIOD = 20
DYNASTY_LOGOUT_DELAY = 5
WITHDRAWAL_DELAY = 5
BASE_INTEREST_FACTOR = 0.02
BASE_PENALTY_FACTOR = 0.002
MIN_DEPOSIT_SIZE = 1000 * 10**18  # 1000 ether

FUNDED_PRIVKEYS = [tester.k1, tester.k2, tester.k3, tester.k4, tester.k5]
DEPOSIT_AMOUNTS = [
    2000 * 10**18,
    # 1000 * 10**18,
]


@pytest.fixture
def fake_hash():
    return b'\xbc' * 32


@pytest.fixture
def base_sender_privkey():
    return tester.k0


@pytest.fixture(params=FUNDED_PRIVKEYS[0:1])
def funded_privkey(request):
    return request.param


@pytest.fixture
def funded_privkeys():
    return FUNDED_PRIVKEYS


@pytest.fixture(params=DEPOSIT_AMOUNTS)
def deposit_amount(request):
    return request.param


@pytest.fixture
def vyper_rlp_decoder_tx():
    return rlp.hex_decode(VYPER_RLP_DECODER_TX_HEX, Transaction)


@pytest.fixture
def vyper_rlp_decoder_address(vyper_rlp_decoder_tx):
    return vyper_rlp_decoder_tx.creates


@pytest.fixture
def msg_hasher_tx():
    return rlp.hex_decode(MSG_HASHER_TX_HEX, Transaction)


@pytest.fixture
def msg_hasher_address(msg_hasher_tx):
    return msg_hasher_tx.creates


@pytest.fixture
def purity_checker_tx():
    return rlp.hex_decode(PURITY_CHECKER_TX_HEX, Transaction)


@pytest.fixture
def purity_checker_address(purity_checker_tx):
    return purity_checker_tx.creates


@pytest.fixture
def purity_checker_ct():
    return ContractTranslator(PURITY_CHECKER_ABI)


@pytest.fixture
def epoch_length():
    return EPOCH_LENGTH


@pytest.fixture
def warm_up_period():
    return WARM_UP_PERIOD


@pytest.fixture
def withdrawal_delay():
    return WITHDRAWAL_DELAY


@pytest.fixture
def dynasty_logout_delay():
    return DYNASTY_LOGOUT_DELAY


@pytest.fixture
def base_interest_factor():
    return BASE_INTEREST_FACTOR


@pytest.fixture
def base_penalty_factor():
    return BASE_PENALTY_FACTOR


@pytest.fixture
def min_deposit_size():
    return MIN_DEPOSIT_SIZE


@pytest.fixture
def casper_config(epoch_length, warm_up_period, withdrawal_delay, dynasty_logout_delay,
                  base_interest_factor, base_penalty_factor, min_deposit_size):
    return {
        "epoch_length": epoch_length,  # in blocks
        "warm_up_period": warm_up_period,  # in blocks
        "withdrawal_delay": withdrawal_delay,  # in epochs
        "dynasty_logout_delay": dynasty_logout_delay,  # in dynasties
        "base_interest_factor": base_interest_factor,
        "base_penalty_factor": base_penalty_factor,
        "min_deposit_size": min_deposit_size
    }


@pytest.fixture
def casper_args(casper_config, msg_hasher_address, purity_checker_address):
    return [
        casper_config["epoch_length"], casper_config["warm_up_period"],
        casper_config["withdrawal_delay"], casper_config["dynasty_logout_delay"],
        msg_hasher_address, purity_checker_address, casper_config["base_interest_factor"],
        casper_config["base_penalty_factor"], casper_config["min_deposit_size"]
    ]


@pytest.fixture
def test_chain(alloc=tester.base_alloc, genesis_gas_limit=9999999,
               min_gas_limit=5000, startgas=3141592):
    # genesis
    header = {
        "number": 0, "gas_limit": genesis_gas_limit,
        "gas_used": 0, "timestamp": 1467446877, "difficulty": 1,
        "uncles_hash": '0x'+utils.encode_hex(utils.sha3(rlp.encode([])))
    }
    genesis = mk_basic_state(alloc, header, tester.get_env(None))
    # tester
    tester.languages['vyper'] = compiler.Compiler()
    tester.STARTGAS = startgas
    chain = tester.Chain(alloc=alloc, genesis=genesis)
    chain.chain.env.config['MIN_GAS_LIMIT'] = min_gas_limit
    chain.mine(1)
    return chain


@pytest.fixture
def casper_code():
    with open(get_dirs('simple_casper.v.py')[0]) as f:
        return f.read()


@pytest.fixture
def casper_abi(casper_code):
    return compiler.mk_full_signature(casper_code)


@pytest.fixture
def casper_ct(casper_abi):
    return ContractTranslator(casper_abi)


@pytest.fixture
def dependency_transactions(vyper_rlp_decoder_tx, msg_hasher_tx, purity_checker_tx):
    return [vyper_rlp_decoder_tx, msg_hasher_tx, purity_checker_tx]


@pytest.fixture
def casper_address(dependency_transactions, base_sender_privkey):
    mock_tx = Transaction(
        len(dependency_transactions),
        GAS_PRICE,
        500000,
        b'',
        0,
        "0x0"
    ).sign(base_sender_privkey)
    return mock_tx.creates


@pytest.fixture
def casper(casper_chain, casper_abi, casper_address):
    return tester.ABIContract(casper_chain, casper_abi, casper_address)


@pytest.fixture
def casper_chain(
        test_chain,
        casper_args,
        casper_code,
        casper_abi,
        casper_ct,
        casper_address,
        dependency_transactions,
        msg_hasher_address,
        purity_checker_address,
        base_sender_privkey,
        initialize_contract=True):
    init_transactions = []
    nonce = 0
    # Create transactions for instantiating RLP decoder, msg hasher and purity checker,
    # plus transactions for feeding the one-time accounts that generate those transactions
    for tx in dependency_transactions:
        fund_gas_tx = Transaction(
            nonce,
            GAS_PRICE,
            500000,
            tx.sender,
            tx.startgas * tx.gasprice + tx.value,
            ''
        ).sign(base_sender_privkey)
        init_transactions.append(fund_gas_tx)
        init_transactions.append(tx)
        nonce += 1

    for tx in init_transactions:
        if test_chain.head_state.gas_used + tx.startgas > test_chain.head_state.gas_limit:
            test_chain.mine(1)
        test_chain.direct_tx(tx)

    test_chain.mine(1)

    # NOTE: bytecode cannot be compiled before RLP Decoder is deployed to chain
    # otherwise, vyper compiler cannot properly embed RLP decoder address
    casper_bytecode = compiler.compile(casper_code)

    deploy_code = casper_bytecode
    casper_tx = Transaction(
        nonce,
        GAS_PRICE,
        7000000,
        b'',
        0,
        deploy_code
    ).sign(base_sender_privkey)
    test_chain.direct_tx(casper_tx)
    nonce += 1

    test_chain.mine(1)

    # Casper contract needs money for its activity
    casper_fund_tx = Transaction(
        nonce,
        GAS_PRICE,
        5000000,
        casper_tx.creates,
        10**21,
        b''
    ).sign(base_sender_privkey)
    test_chain.direct_tx(casper_fund_tx)

    test_chain.mine(1)

    if initialize_contract:
        casper_contract = casper(test_chain, casper_abi, casper_address)
        casper_contract.init(*casper_args)

    return test_chain


@pytest.fixture
def deploy_casper_contract(
        test_chain,
        casper_code,
        casper_ct,
        casper_abi,
        casper_address,
        dependency_transactions,
        msg_hasher_address,
        purity_checker_address,
        base_sender_privkey):
    def deploy_casper_contract(contract_args, initialize_contract=True):
        chain = casper_chain(
            test_chain, contract_args, casper_code, casper_abi, casper_ct, casper_address,
            dependency_transactions, msg_hasher_address, purity_checker_address,
            base_sender_privkey, initialize_contract
        )
        return casper(chain, casper_abi, casper_address)
    return deploy_casper_contract


def get_dirs(path):
    abs_contract_path = os.path.realpath(os.path.join(OWN_DIR, '..', 'casper', 'contracts'))
    sub_dirs = [x[0] for x in os.walk(abs_contract_path)]
    extra_args = ' '.join(['{}={}'.format(d.split('/')[-1], d) for d in sub_dirs])
    path = '{}/{}'.format(abs_contract_path, path)
    return path, extra_args


# Note: If called during "warm_up-period", new_epoch mines all the way through
# the warm up period until `initialize_epoch` can first be called
@pytest.fixture
def new_epoch(casper_chain, casper):
    def new_epoch():
        next_epoch = casper.current_epoch() + 1
        epoch_length = casper.EPOCH_LENGTH()

        casper_chain.mine(epoch_length * next_epoch - casper_chain.head_state.block_number)
        casper.initialize_epoch(next_epoch)
    return new_epoch


@pytest.fixture
def mk_validation_code():
    def mk_validation_code(address, valcode_type):
        return compile_valcode_to_evm_bytecode(valcode_type, address)
    return mk_validation_code


@pytest.fixture
def mk_vote():
    def mk_vote(validator_index, target_hash, target_epoch, source_epoch, privkey):
        msg_hash = utils.sha3(
            rlp.encode([validator_index, target_hash, target_epoch, source_epoch])
        )
        v, r, s = utils.ecdsa_raw_sign(msg_hash, privkey)
        sig = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
        return rlp.encode([validator_index, target_hash, target_epoch, source_epoch, sig])
    return mk_vote


@pytest.fixture
def mk_suggested_vote(casper, mk_vote):
    def mk_suggested_vote(validator_index, privkey):
        target_hash = casper.recommended_target_hash()
        target_epoch = casper.current_epoch()
        source_epoch = casper.recommended_source_epoch()
        return mk_vote(validator_index, target_hash, target_epoch, source_epoch, privkey)
    return mk_suggested_vote


@pytest.fixture
def mk_slash_votes(casper, mk_vote, fake_hash):
    def mk_slash_votes(validator_index, privkey):
        vote_1 = mk_vote(
            validator_index,
            casper.recommended_target_hash(),
            casper.current_epoch(),
            casper.recommended_source_epoch(),
            privkey
        )
        vote_2 = mk_vote(
            validator_index,
            fake_hash,
            casper.current_epoch(),
            casper.recommended_source_epoch(),
            privkey
        )
        return vote_1, vote_2
    return mk_slash_votes


@pytest.fixture
def mk_logout_msg_signed():
    def mk_logout_msg_signed(validator_index, epoch, key):
        msg_hash = utils.sha3(rlp.encode([validator_index, epoch]))
        v, r, s = utils.ecdsa_raw_sign(msg_hash, key)
        sig = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
        return rlp.encode([validator_index, epoch, sig])
    return mk_logout_msg_signed


@pytest.fixture
def mk_logout_msg_unsigned():
    def mk_logout_msg_unsigned(validator_index, epoch):
        v, r, s = (0, 0, 0)
        sig = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
        return rlp.encode([validator_index, epoch, sig])
    return mk_logout_msg_unsigned


@pytest.fixture
def logout_validator_via_signed_msg(casper, mk_logout_msg_signed):
    def logout_validator_via_signed_msg(validator_index, msg_signing_key,
                                        tx_sender_key=42):
        logout_tx = mk_logout_msg_signed(
            validator_index,
            casper.current_epoch(),
            msg_signing_key
        )
        casper.logout(logout_tx, sender=tx_sender_key)
    return logout_validator_via_signed_msg


@pytest.fixture
def logout_validator_via_unsigned_msg(casper, mk_logout_msg_unsigned):
    def logout_validator_via_unsigned_msg(validator_index, tx_sender_key):
        logout_tx = mk_logout_msg_unsigned(validator_index, casper.current_epoch())
        casper.logout(logout_tx, sender=tx_sender_key)
    return logout_validator_via_unsigned_msg


@pytest.fixture
def validation_addr(casper_chain, casper, mk_validation_code):
    def validation_addr(privkey, valcode_type):
        addr = utils.privtoaddr(privkey)
        return casper_chain.tx(
            privkey,
            "",
            0,
            mk_validation_code(addr, valcode_type)
        )
    return validation_addr


@pytest.fixture
def deposit_validator(casper_chain, casper, validation_addr):
    def deposit_validator(privkey, value, valcode_type="pure_ecrecover"):
        addr = utils.privtoaddr(privkey)
        valcode_addr = validation_addr(privkey, valcode_type)
        casper.deposit(valcode_addr, addr, value=value)
        return casper.validator_indexes(addr)
    return deposit_validator


# deposits privkey, value and steps forward two epochs
# to step dynasties forward to induct validator
# NOTE: This method only works when no deposits exist and chain insta-finalizes
#       If inducting a validator when desposits exists, use `deposit_validator` and
#       manually finalize
@pytest.fixture
def induct_validator(casper_chain, casper, deposit_validator, new_epoch):
    def induct_validator(privkey, value, valcode_type="pure_ecrecover"):
        validator_index = deposit_validator(privkey, value, valcode_type)
        new_epoch()  # justify
        new_epoch()  # finalize and increment dynasty
        new_epoch()  # finalize and increment dynasty
        return validator_index
    return induct_validator


# deposits list of (privkey, value) and steps forward two epochs
# to step dynasties forward to induct validators
# NOTE: This method only works when no deposits exist and chain insta-finalizes
#       If inducting validators when desposits exists, use `deposit_validator` and
#       manually finalize
@pytest.fixture
def induct_validators(casper_chain, casper, deposit_validator, new_epoch):
    def induct_validators(privkeys, values):
        start_index = casper.next_validator_index()
        for privkey, value in zip(privkeys, values):
            deposit_validator(privkey, value)
        new_epoch()  # justify
        new_epoch()  # finalize and increment dynasty
        new_epoch()  # finalize and increment dynasty
        return list(range(start_index, start_index + len(privkeys)))
    return induct_validators


@pytest.fixture
def assert_failed():
    def assert_failed(function_to_test, exception):
        with pytest.raises(exception):
            function_to_test()
    return assert_failed


@pytest.fixture
def assert_tx_failed(test_chain):
    def assert_tx_failed(function_to_test, exception=tester.TransactionFailed):
        initial_state = test_chain.snapshot()
        with pytest.raises(exception):
            function_to_test()
        test_chain.revert(initial_state)
    return assert_tx_failed


@pytest.fixture
def get_logs():
    def get_logs(receipt, contract, event_name=None):
        contract_log_ids = contract.translator.event_data.keys() # All the log ids contract has
        # All logs originating from contract, and matching event_name (if specified)
        logs = [log for log in receipt.logs \
                if log.topics[0] in contract_log_ids and \
                log.address == contract.address and \
                (not event_name or \
                 contract.translator.event_data[log.topics[0]]['name'] == event_name)]
        assert len(logs) > 0, "No logs in last receipt"

        # Return all events decoded in the receipt
        return [contract.translator.decode_event(log.topics, log.data) for log in logs]
    return get_logs


@pytest.fixture
def get_last_log(get_logs):
    def get_last_log(casper_chain, contract, event_name=None):
        receipt = casper_chain.head_state.receipts[-1] # Only the receipts for the last block
        # Get last log event with correct name and return the decoded event
        return get_logs(receipt, contract, event_name=event_name)[-1]
    return get_last_log
