import pytest
import os
import rlp

from ethereum.abi import ContractTranslator
from ethereum.genesis_helpers import mk_basic_state
from ethereum.transactions import Transaction
from ethereum.tools import tester
from ethereum import utils
from vyper import compiler


OWN_DIR = os.path.dirname(os.path.realpath(__file__))

GAS_PRICE = 25 * 10**9

VYPER_RLP_DECODER_TX_HEX = "0xf9035b808506fc23ac0083045f788080b903486103305660006109ac5260006109cc527f0100000000000000000000000000000000000000000000000000000000000000600035046109ec526000610a0c5260006109005260c06109ec51101515585760f86109ec51101561006e5760bf6109ec510336141558576001610a0c52610098565b60013560f76109ec51036020035260005160f66109ec510301361415585760f66109ec5103610a0c525b61022060016064818352015b36610a0c511015156100b557610291565b7f0100000000000000000000000000000000000000000000000000000000000000610a0c5135046109ec526109cc5160206109ac51026040015260016109ac51016109ac5260806109ec51101561013b5760016109cc5161044001526001610a0c516109cc5161046001376001610a0c5101610a0c5260216109cc51016109cc52610281565b60b86109ec5110156101d15760806109ec51036109cc51610440015260806109ec51036001610a0c51016109cc51610460013760816109ec5114156101ac5760807f01000000000000000000000000000000000000000000000000000000000000006001610a0c5101350410151558575b607f6109ec5103610a0c5101610a0c5260606109ec51036109cc51016109cc52610280565b60c06109ec51101561027d576001610a0c51013560b76109ec510360200352600051610a2c526038610a2c5110157f01000000000000000000000000000000000000000000000000000000000000006001610a0c5101350402155857610a2c516109cc516104400152610a2c5160b66109ec5103610a0c51016109cc516104600137610a2c5160b66109ec5103610a0c510101610a0c526020610a2c51016109cc51016109cc5261027f565bfe5b5b5b81516001018083528114156100a4575b5050601f6109ac511115155857602060206109ac5102016109005260206109005103610a0c5261022060016064818352015b6000610a0c5112156102d45761030a565b61090051610a0c516040015101610a0c51610900516104400301526020610a0c5103610a0c5281516001018083528114156102c3575b50506109cc516109005101610420526109cc5161090051016109005161044003f35b61000461033003610004600039610004610330036000f31b2d4f"  # NOQA
SIG_HASHER_TX_HEX = "0xf9016d808506fc23ac0083026a508080b9015a6101488061000e6000396101565660007f01000000000000000000000000000000000000000000000000000000000000006000350460f8811215610038576001915061003f565b60f6810391505b508060005b368312156100c8577f01000000000000000000000000000000000000000000000000000000000000008335048391506080811215610087576001840193506100c2565b60b881121561009d57607f8103840193506100c1565b60c08112156100c05760b68103600185013560b783036020035260005101840193505b5b5b50610044565b81810360388112156100f4578060c00160005380836001378060010160002060e052602060e0f3610143565b61010081121561010557600161011b565b6201000081121561011757600261011a565b60035b5b8160005280601f038160f701815382856020378282600101018120610140526020610140f350505b505050505b6000f31b2d4f"  # NOQA
PURITY_CHECKER_TX_HEX = "0xf90467808506fc23ac00830583c88080b904546104428061000e60003961045056600061033f537c0100000000000000000000000000000000000000000000000000000000600035047f80010000000000000000000000000000000000000030ffff1c0e00000000000060205263a1903eab8114156103f7573659905901600090523660048237600435608052506080513b806020015990590160009052818152602081019050905060a0526080513b600060a0516080513c6080513b8060200260200159905901600090528181526020810190509050610100526080513b806020026020015990590160009052818152602081019050905061016052600060005b602060a05103518212156103c957610100601f8360a051010351066020518160020a161561010a57fe5b80606013151561011e57607f811315610121565b60005b1561014f5780607f036101000a60018460a0510101510482602002610160510152605e8103830192506103b2565b60f18114801561015f5780610164565b60f282145b905080156101725780610177565b60f482145b9050156103aa5760028212151561019e5760606001830360200261010051015112156101a1565b60005b156101bc57607f6001830360200261010051015113156101bf565b60005b156101d157600282036102605261031e565b6004821215156101f057600360018303602002610100510151146101f3565b60005b1561020d57605a6002830360200261010051015114610210565b60005b1561022b57606060038303602002610100510151121561022e565b60005b1561024957607f60038303602002610100510151131561024c565b60005b1561025e57600482036102605261031d565b60028212151561027d57605a6001830360200261010051015114610280565b60005b1561029257600282036102605261031c565b6002821215156102b157609060018303602002610100510151146102b4565b60005b156102c657600282036102605261031b565b6002821215156102e65760806001830360200261010051015112156102e9565b60005b156103035760906001830360200261010051015112610306565b60005b1561031857600282036102605261031a565bfe5b5b5b5b5b604060405990590160009052600081526102605160200261016051015181602001528090502054156103555760016102a052610393565b60306102605160200261010051015114156103755760016102a052610392565b60606102605160200261010051015114156103915760016102a0525b5b5b6102a051151561039f57fe5b6001830192506103b1565b6001830192505b5b8082602002610100510152600182019150506100e0565b50506001604060405990590160009052600081526080518160200152809050205560016102e05260206102e0f35b63c23697a8811415610440573659905901600090523660048237600435608052506040604059905901600090526000815260805181602001528090502054610300526020610300f35b505b6000f31b2d4f"  # NOQA
PURITY_CHECKER_ABI = [{'name': 'check(address)', 'type': 'function', 'constant': True, 'inputs': [{'name': 'addr', 'type': 'address'}], 'outputs': [{'name': 'out', 'type': 'bool'}]}, {'name': 'submit(address)', 'type': 'function', 'constant': False, 'inputs': [{'name': 'addr', 'type': 'address'}], 'outputs': [{'name': 'out', 'type': 'bool'}]}]  # NOQA

EPOCH_LENGTH = 10
DYNASTY_LOGOUT_DELAY = 5
WITHDRAWAL_DELAY = 5
OWNER = utils.checksum_encode(tester.a0)
BASE_INTEREST_FACTOR = 0.02
BASE_PENALTY_FACTOR = 0.002
MIN_DEPOSIT_SIZE = 1000 * 10**18  # 1000 ether

CASPER_CONFIG = {
    "epoch_length": EPOCH_LENGTH,  # in blocks
    "withdrawal_delay": WITHDRAWAL_DELAY,  # in epochs
    "dynasty_logout_delay": DYNASTY_LOGOUT_DELAY,  # in dynasties
    "owner": OWNER,  # Backdoor address
    "base_interest_factor": BASE_INTEREST_FACTOR,
    "base_penalty_factor": BASE_PENALTY_FACTOR,
    "min_deposit_size": MIN_DEPOSIT_SIZE
}

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
def sig_hasher_tx():
    return rlp.hex_decode(SIG_HASHER_TX_HEX, Transaction)


@pytest.fixture
def sig_hasher_address(sig_hasher_tx):
    return sig_hasher_tx.creates


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
def casper_config():
    return CASPER_CONFIG


@pytest.fixture
def casper_args(casper_config, sig_hasher_address, purity_checker_address):
    return [
        casper_config["epoch_length"], casper_config["withdrawal_delay"],
        casper_config["dynasty_logout_delay"], casper_config["owner"],
        sig_hasher_address, purity_checker_address, casper_config["base_interest_factor"],
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
def dependency_transactions(vyper_rlp_decoder_tx, sig_hasher_tx, purity_checker_tx):
    return [vyper_rlp_decoder_tx, sig_hasher_tx, purity_checker_tx]


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
        casper_ct,
        dependency_transactions,
        sig_hasher_address,
        purity_checker_address,
        base_sender_privkey):
    init_transactions = []
    nonce = 0
    # Create transactions for instantiating RLP decoder, sig hasher and purity checker,
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

    init_args = casper_ct.encode_constructor_arguments(casper_args)

    deploy_code = casper_bytecode + (init_args)
    casper_tx = Transaction(
        nonce,
        GAS_PRICE,
        5000000,
        b'',
        0,
        deploy_code
    ).sign(base_sender_privkey)
    test_chain.direct_tx(casper_tx)
    nonce += 1

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
    return test_chain


def get_dirs(path):
    abs_contract_path = os.path.realpath(os.path.join(OWN_DIR, '..', 'casper', 'contracts'))
    sub_dirs = [x[0] for x in os.walk(abs_contract_path)]
    extra_args = ' '.join(['{}={}'.format(d.split('/')[-1], d) for d in sub_dirs])
    path = '{}/{}'.format(abs_contract_path, path)
    return path, extra_args


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
    def mk_validation_code(address):
        """
        validation_code = '''
        ~calldatacopy(0, 0, 128)
        ~call(3000, 1, 0, 0, 128, 0, 32)
        return(~mload(0) == {})
        '''.format(utils.checksum_encode(address))
        return serpent.compile(validation_code)
        """
        # The precompiled bytecode of the validation code which
        # verifies EC signatures
        validation_code_bytecode = b"a\x009\x80a\x00\x0e`\x009a\x00GV`\x80`\x00`\x007` "
        validation_code_bytecode += b"`\x00`\x80`\x00`\x00`\x01a\x0b\xb8\xf1Ps"
        validation_code_bytecode += address
        validation_code_bytecode += b"`\x00Q\x14` R` ` \xf3[`\x00\xf3"
        return validation_code_bytecode
    return mk_validation_code


@pytest.fixture
def mk_vote():
    def mk_vote(validator_index, target_hash, target_epoch, source_epoch, privkey):
        sighash = utils.sha3(
            rlp.encode([validator_index, target_hash, target_epoch, source_epoch])
        )
        v, r, s = utils.ecdsa_raw_sign(sighash, privkey)
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
def mk_logout():
    def mk_logout(validator_index, epoch, key):
        sighash = utils.sha3(rlp.encode([validator_index, epoch]))
        v, r, s = utils.ecdsa_raw_sign(sighash, key)
        sig = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
        return rlp.encode([validator_index, epoch, sig])
    return mk_logout


@pytest.fixture
def logout_validator(casper, mk_logout):
    def logout_validator(validator_index, key):
        logout_tx = mk_logout(validator_index, casper.current_epoch(), key)
        casper.logout(logout_tx)
    return logout_validator


@pytest.fixture
def validation_addr(casper_chain, casper, mk_validation_code):
    def validation_addr(privkey):
        addr = utils.privtoaddr(privkey)
        return casper_chain.tx(
            privkey,
            "",
            0,
            mk_validation_code(addr)
        )
    return validation_addr


@pytest.fixture
def deposit_validator(casper_chain, casper, validation_addr):
    def deposit_validator(privkey, value):
        addr = utils.privtoaddr(privkey)
        valcode_addr = validation_addr(privkey)
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
    def induct_validator(privkey, value):
        if casper.current_epoch() == 0:
            new_epoch()
        validator_index = deposit_validator(privkey, value)
        new_epoch()
        new_epoch()
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
        if casper.current_epoch() == 0:
            new_epoch()
        for privkey, value in zip(privkeys, values):
            deposit_validator(privkey, value)
        new_epoch()
        new_epoch()
        return list(range(start_index, start_index + len(privkeys)))
    return induct_validators


@pytest.fixture
def assert_failed(casper_chain):
    def assert_failed(function_to_test, exception):
        with pytest.raises(exception):
            function_to_test()
    return assert_failed


@pytest.fixture
def assert_tx_failed(casper_chain):
    def assert_tx_failed(function_to_test, exception=tester.TransactionFailed):
        initial_state = casper_chain.snapshot()
        with pytest.raises(exception):
            function_to_test()
        casper_chain.revert(initial_state)
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
