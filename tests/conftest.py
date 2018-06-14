import pytest
import os
import rlp

from decimal import (
    Decimal,
)

import eth_tester
from eth_tester import (
    EthereumTester,
    PyEVMBackend
)
from web3.providers.eth_tester import (
    EthereumTesterProvider,
)
from web3 import (
    Web3,
)
from web3.contract import (
    ConciseContract,
)
from vyper import (
    compiler,
    utils as vyper_utils,
)

from utils.utils import encode_int32
from utils.valcodes import compile_valcode_to_evm_bytecode

OWN_DIR = os.path.dirname(os.path.realpath(__file__))

GAS_PRICE = 25 * 10**9

NULL_SENDER = '0xffffffffffffffffffffffffffffffffffffffff'
CASPER_ADDRESS = "0x0000000000000000000000000000000000000042"

VYPER_RLP_DECODER_TX_HEX = "0xf9035b808506fc23ac0083045f788080b903486103305660006109ac5260006109cc527f0100000000000000000000000000000000000000000000000000000000000000600035046109ec526000610a0c5260006109005260c06109ec51101515585760f86109ec51101561006e5760bf6109ec510336141558576001610a0c52610098565b60013560f76109ec51036020035260005160f66109ec510301361415585760f66109ec5103610a0c525b61022060016064818352015b36610a0c511015156100b557610291565b7f0100000000000000000000000000000000000000000000000000000000000000610a0c5135046109ec526109cc5160206109ac51026040015260016109ac51016109ac5260806109ec51101561013b5760016109cc5161044001526001610a0c516109cc5161046001376001610a0c5101610a0c5260216109cc51016109cc52610281565b60b86109ec5110156101d15760806109ec51036109cc51610440015260806109ec51036001610a0c51016109cc51610460013760816109ec5114156101ac5760807f01000000000000000000000000000000000000000000000000000000000000006001610a0c5101350410151558575b607f6109ec5103610a0c5101610a0c5260606109ec51036109cc51016109cc52610280565b60c06109ec51101561027d576001610a0c51013560b76109ec510360200352600051610a2c526038610a2c5110157f01000000000000000000000000000000000000000000000000000000000000006001610a0c5101350402155857610a2c516109cc516104400152610a2c5160b66109ec5103610a0c51016109cc516104600137610a2c5160b66109ec5103610a0c510101610a0c526020610a2c51016109cc51016109cc5261027f565bfe5b5b5b81516001018083528114156100a4575b5050601f6109ac511115155857602060206109ac5102016109005260206109005103610a0c5261022060016064818352015b6000610a0c5112156102d45761030a565b61090051610a0c516040015101610a0c51610900516104400301526020610a0c5103610a0c5281516001018083528114156102c3575b50506109cc516109005101610420526109cc5161090051016109005161044003f35b61000461033003610004600039610004610330036000f31b2d4f"  # NOQA
VYPER_RLP_DECODER_TX_SENDER = "0x39ba083c30fCe59883775Fc729bBE1f9dE4DEe11"
MSG_HASHER_TX_HEX = "0xf9016d808506fc23ac0083026a508080b9015a6101488061000e6000396101565660007f01000000000000000000000000000000000000000000000000000000000000006000350460f8811215610038576001915061003f565b60f6810391505b508060005b368312156100c8577f01000000000000000000000000000000000000000000000000000000000000008335048391506080811215610087576001840193506100c2565b60b881121561009d57607f8103840193506100c1565b60c08112156100c05760b68103600185013560b783036020035260005101840193505b5b5b50610044565b81810360388112156100f4578060c00160005380836001378060010160002060e052602060e0f3610143565b61010081121561010557600161011b565b6201000081121561011757600261011a565b60035b5b8160005280601f038160f701815382856020378282600101018120610140526020610140f350505b505050505b6000f31b2d4f"  # NOQA
MSG_HASHER_TX_SENDER = "0xD7a3BD6C9eA32efF147d067f907AE6b22d436F91"
PURITY_CHECKER_TX_HEX = "0xf90403808506fc23ac0083061a808080b903f06103d856600035601c52740100000000000000000000000000000000000000006020526f7fffffffffffffffffffffffffffffff6040527fffffffffffffffffffffffffffffffff8000000000000000000000000000000060605274012a05f1fffffffffffffffffffffffffdabf41c006080527ffffffffffffffffffffffffed5fa0e000000000000000000000000000000000060a05263a1903eab600051141561038657602060046101403734156100b457600080fd5b60043560205181106100c557600080fd5b50610140513b60008114156100da57fe610367565b806000610160610140513c806041026101600160008160007fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff818352015b84845110151561012b5761036256610351565b610100601f8551036101600151068060020a7f80010000000000000000000000000000000000000030ffff1c0e000000000000161561016657fe5b607f811115816060111516156101a55780607f036101000a600186516101600101510484602002876021026101600101528451605f820301855261033d565b60f4811460f282141760f18214171561033c576000607f6001860360200288610160010151111560606001870360200289610160010151101516600286101516156101f5576002850390506102e2565b607f6003860360200288610160010151111560606003870360200289610160010151101516605a6002870360200289610160010151141660036001870360200289610160010151141660048610151615610254576004850390506102e1565b605a6001860360200288610160010151146002861015161561027b576002850390506102e0565b6090600186036020028861016001015114600286101516156102a2576002850390506102df565b609060018603602002886101600101511060806001870360200289610160010151101516600286101516156102dc576002850390506102de565bfe5b5b5b5b5b8060200287602102610160010151600060c052602060c0200154156103065761033a565b60308160200288610160010151141561031e57610339565b60608160200288610160010151141561033657610338565bfe5b5b5b505b5b808460200287610160010152600184019350505b5b8151600101808352811415610118575b505050505b50600161014051600060c052602060c0200155600160005260206000f3005b63c23697a860005114156103d357602060046101403734156103a757600080fd5b60043560205181106103b857600080fd5b5061014051600060c052602060c020015460005260206000f3005b5b6100046103d8036100046000396100046103d8036000f31b2d4f"  # NOQA
PURITY_CHECKER_TX_SENDER = "0xBbED7124dB2543ac17c2096961a59a9C0095FA78"
PURITY_CHECKER_ABI = [{'name': 'check', 'type': 'function', 'constant': True, 'inputs': [{'name': 'addr', 'type': 'address'}], 'outputs': [{'name': 'out', 'type': 'bool'}]}, {'name': 'submit', 'type': 'function', 'constant': False, 'inputs': [{'name': 'addr', 'type': 'address'}], 'outputs': [{'name': 'out', 'type': 'bool'}]}]  # NOQA

EPOCH_LENGTH = 10
WARM_UP_PERIOD = 20
DYNASTY_LOGOUT_DELAY = 5
WITHDRAWAL_DELAY = 8
BASE_INTEREST_FACTOR = Decimal('0.02')
BASE_PENALTY_FACTOR = Decimal('0.002')
MIN_DEPOSIT_SIZE = 1000 * 10**18  # 1000 ether

DEPOSIT_AMOUNTS = [
    2000 * 10**18,
    # 1000 * 10**18,
]


setattr(eth_tester.backends.pyevm.main, 'GENESIS_GAS_LIMIT', 10**9)
setattr(eth_tester.backends.pyevm.main, 'GENESIS_DIFFICULTY', 1)


@pytest.fixture
def next_contract_address(w3, base_tester, fake_contract_code):
    def next_contract_address(sender):
        snapshot_id = base_tester.take_snapshot()
        bytecode = compiler.compile(fake_contract_code)
        hex_bytecode = Web3.toHex(bytecode)
        tx_hash = w3.eth.sendTransaction({
            'from': sender,
            'to': '',
            'gas': 7000000,
            'data': hex_bytecode
        })
        contract_address = w3.eth.getTransactionReceipt(tx_hash).contractAddress

        base_tester.revert_to_snapshot(snapshot_id)
        return contract_address
    return next_contract_address


@pytest.fixture
def fake_hash():
    return b'\xbc' * 32


@pytest.fixture
def fake_contract_code():
    return '''
@public
def five() -> int128:
     return 5
'''


@pytest.fixture
def base_sender(base_tester):
    return base_tester.get_accounts()[-1]


@pytest.fixture
def funded_accounts(base_tester):
    return base_tester.get_accounts()[0:5]


@pytest.fixture
def funded_account(funded_accounts):
    return funded_accounts[0]


@pytest.fixture
def validation_keys(w3, funded_accounts):
    # use address as the keymash to gen new private keys
    # insecure but fine for our purposes
    return [w3.eth.account.create(str(address)).privateKey for address in funded_accounts]


@pytest.fixture
def validation_key(validation_keys):
    return validation_keys[0]


@pytest.fixture
def validation_addrs(w3, validation_keys):
    return [w3.eth.account.privateKeyToAccount(key).address for key in validation_keys]


@pytest.fixture(params=DEPOSIT_AMOUNTS)
def deposit_amount(request):
    return request.param


@pytest.fixture
def vyper_rlp_decoder_address():
    tmp_tester = EthereumTester(PyEVMBackend())
    tmp_w3 = w3(tmp_tester)
    address = deploy_rlp_decoder(tmp_w3)()
    return address


@pytest.fixture
def msg_hasher_address():
    tmp_tester = EthereumTester(PyEVMBackend())
    tmp_w3 = w3(tmp_tester)
    address = deploy_msg_hasher(tmp_w3)()
    return address


@pytest.fixture
def purity_checker_address():
    tmp_tester = EthereumTester(PyEVMBackend())
    tmp_w3 = w3(tmp_tester)
    address = deploy_purity_checker(tmp_w3)()
    return address


@pytest.fixture
def purity_checker(w3, purity_checker_address):
    purity_checker = w3.eth.contract(
        address=purity_checker_address,
        abi=PURITY_CHECKER_ABI
    )
    return purity_checker


@pytest.fixture
def null_sender(base_tester):
    return base_tester.get_accounts()[-2]


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
def casper_config(epoch_length,
                  warm_up_period,
                  withdrawal_delay,
                  dynasty_logout_delay,
                  base_interest_factor,
                  base_penalty_factor,
                  min_deposit_size):
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
def casper_args(casper_config,
                msg_hasher_address,
                purity_checker_address,
                null_sender):
    return [
        casper_config["epoch_length"],
        casper_config["warm_up_period"],
        casper_config["withdrawal_delay"],
        casper_config["dynasty_logout_delay"],
        msg_hasher_address,
        purity_checker_address,
        null_sender,
        casper_config["base_interest_factor"],
        casper_config["base_penalty_factor"],
        casper_config["min_deposit_size"]
    ]


@pytest.fixture
def base_tester():
    return EthereumTester(PyEVMBackend())


def zero_gas_price_strategy(web3, transaction_params=None):
    return 0  # zero gas price makes testing simpler.


@pytest.fixture
def w3(base_tester):
    web3 = Web3(EthereumTesterProvider(base_tester))
    web3.eth.setGasPriceStrategy(zero_gas_price_strategy)
    return web3


@pytest.fixture
def tester(w3,
           base_tester,
           casper_args,
           casper_code,
           casper_abi,
           casper_address,
           deploy_rlp_decoder,
           deploy_msg_hasher,
           deploy_purity_checker,
           base_sender,
           initialize_contract=True):
    deploy_rlp_decoder()
    deploy_msg_hasher()
    deploy_purity_checker()

    # NOTE: bytecode cannot be compiled before RLP Decoder is deployed to chain
    # otherwise, vyper compiler cannot properly embed RLP decoder address
    casper_bytecode = compiler.compile(casper_code, bytecode_runtime=True)

    chain = base_tester.backend.chain
    vm = chain.get_vm()

    vm.state.account_db.set_code(Web3.toBytes(hexstr=casper_address), casper_bytecode)
    vm.state.account_db.persist()
    new_state_root = vm.state.account_db.state_root

    new_header = chain.header.copy(state_root=new_state_root)
    chain.header = new_header

    # mine block to ensure we don't have mismatched state
    base_tester.mine_block()

    # Casper contract needs money for its activity
    w3.eth.sendTransaction({
        'to': casper_address,
        'value': 10**21
    })

    if initialize_contract:
        casper_contract = casper(w3, base_tester, casper_abi, casper_address)
        casper_contract.functions.init(*casper_args).transact()

    return base_tester


@pytest.fixture
def deploy_rlp_decoder(w3):
    def deploy_rlp_decoder():
        w3.eth.sendTransaction({
            'to': VYPER_RLP_DECODER_TX_SENDER,
            'value': 10**17
        })
        tx_hash = w3.eth.sendRawTransaction(VYPER_RLP_DECODER_TX_HEX)

        receipt = w3.eth.getTransactionReceipt(tx_hash)
        contract_address = receipt.contractAddress
        assert vyper_utils.RLP_DECODER_ADDRESS == w3.toInt(hexstr=contract_address)
        return contract_address
    return deploy_rlp_decoder


@pytest.fixture
def deploy_msg_hasher(w3):
    def deploy_msg_hasher():
        w3.eth.sendTransaction({
            'to': MSG_HASHER_TX_SENDER,
            'value': 10**17
        })
        tx_hash = w3.eth.sendRawTransaction(MSG_HASHER_TX_HEX)

        receipt = w3.eth.getTransactionReceipt(tx_hash)
        return receipt.contractAddress
    return deploy_msg_hasher


@pytest.fixture
def deploy_purity_checker(w3):
    def deploy_purity_checker():
        w3.eth.sendTransaction({
            'to': PURITY_CHECKER_TX_SENDER,
            'value': 10**17
        })
        tx_hash = w3.eth.sendRawTransaction(PURITY_CHECKER_TX_HEX)

        receipt = w3.eth.getTransactionReceipt(tx_hash)
        return receipt.contractAddress
    return deploy_purity_checker


@pytest.fixture
def casper_code():
    with open(get_dirs('simple_casper.v.py')[0]) as f:
        return f.read()


@pytest.fixture
def casper_abi(casper_code):
    return compiler.mk_full_signature(casper_code)


@pytest.fixture
def casper_address():
    return CASPER_ADDRESS


@pytest.fixture
def casper_deposit_filter(casper):
    return casper.events.Deposit.createFilter(fromBlock='latest')


@pytest.fixture
def casper_vote_filter(casper):
    return casper.events.Vote.createFilter(fromBlock='latest')


@pytest.fixture
def casper_logout_filter(casper):
    return casper.events.Logout.createFilter(fromBlock='latest')


@pytest.fixture
def casper_withdraw_filter(casper):
    return casper.events.Withdraw.createFilter(fromBlock='latest')


@pytest.fixture
def casper_slash_filter(casper):
    return casper.events.Slash.createFilter(fromBlock='latest')


@pytest.fixture
def casper_epoch_filter(casper):
    return casper.events.Epoch.createFilter(fromBlock='latest')


@pytest.fixture
def casper(w3, tester, casper_abi, casper_address):
    casper = w3.eth.contract(
        address=casper_address,
        abi=casper_abi
    )
    return casper


@pytest.fixture
def concise_casper(casper):
    return ConciseContract(casper)


@pytest.fixture
def deploy_casper_contract(
        w3,
        base_tester,
        casper_code,
        casper_abi,
        casper_address,
        deploy_rlp_decoder,
        deploy_msg_hasher,
        deploy_purity_checker,
        base_sender):
    def deploy_casper_contract(contract_args, initialize_contract=True):
        t = tester(
            w3, base_tester, contract_args, casper_code, casper_abi, casper_address,
            deploy_rlp_decoder, deploy_msg_hasher, deploy_purity_checker,
            base_sender, initialize_contract
        )
        return casper(w3, t, casper_abi, casper_address)
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
def new_epoch(tester, casper, epoch_length):
    def new_epoch():
        block_number = tester.get_block_by_number('latest')['number']
        current_epoch = casper.functions.current_epoch().call()
        next_epoch = current_epoch + 1

        tester.mine_blocks(epoch_length * next_epoch - block_number)

        casper.functions.initialize_epoch(next_epoch).transact()

    return new_epoch


@pytest.fixture
def mk_validation_code():
    def mk_validation_code(address, valcode_type):
        return compile_valcode_to_evm_bytecode(valcode_type, address)
    return mk_validation_code


@pytest.fixture
def send_vote(casper, null_sender):
    def send_vote(vote_msg, sender=None):
        if sender is None:
            sender = null_sender

        casper.functions.vote(
            vote_msg
        ).transact({
            'from': sender
        })
    return send_vote


@pytest.fixture
def mk_vote(w3):
    def mk_vote(validator_index, target_hash, target_epoch, source_epoch, validation_key):
        msg_hash = w3.sha3(
            rlp.encode([validator_index, target_hash, target_epoch, source_epoch])
        )
        signed = w3.eth.account.signHash(msg_hash, validation_key)
        sig = encode_int32(signed.v) + encode_int32(signed.r) + encode_int32(signed.s)
        return rlp.encode([validator_index, target_hash, target_epoch, source_epoch, sig])
    return mk_vote


@pytest.fixture
def mk_suggested_vote(concise_casper, mk_vote):
    def mk_suggested_vote(validator_index, validation_key):
        target_hash = concise_casper.recommended_target_hash()
        target_epoch = concise_casper.current_epoch()
        source_epoch = concise_casper.recommended_source_epoch()
        return mk_vote(validator_index, target_hash, target_epoch, source_epoch, validation_key)
    return mk_suggested_vote


@pytest.fixture
def mk_slash_votes(concise_casper, mk_vote, fake_hash):
    def mk_slash_votes(validator_index, validation_key):
        vote_1 = mk_vote(
            validator_index,
            concise_casper.recommended_target_hash(),
            concise_casper.current_epoch(),
            concise_casper.recommended_source_epoch(),
            validation_key
        )
        vote_2 = mk_vote(
            validator_index,
            fake_hash,
            concise_casper.current_epoch(),
            concise_casper.recommended_source_epoch(),
            validation_key
        )
        return vote_1, vote_2
    return mk_slash_votes


@pytest.fixture
def mk_logout_msg_signed(w3):
    def mk_logout_msg_signed(validator_index, epoch, validation_key):
        msg_hash = Web3.sha3(rlp.encode([validator_index, epoch]))
        signed = w3.eth.account.signHash(msg_hash, validation_key)
        sig = encode_int32(signed.v) + encode_int32(signed.r) + encode_int32(signed.s)
        return rlp.encode([validator_index, epoch, sig])
    return mk_logout_msg_signed


@pytest.fixture
def mk_logout_msg_unsigned():
    def mk_logout_msg_unsigned(validator_index, epoch):
        v, r, s = (0, 0, 0)
        sig = encode_int32(v) + encode_int32(r) + encode_int32(s)
        return rlp.encode([validator_index, epoch, sig])
    return mk_logout_msg_unsigned


@pytest.fixture
def logout_validator_via_signed_msg(casper, concise_casper, mk_logout_msg_signed, base_sender):
    def logout_validator_via_signed_msg(validator_index,
                                        msg_signing_key,
                                        tx_sender_addr=base_sender):
        logout_msg = mk_logout_msg_signed(
            validator_index,
            concise_casper.current_epoch(),
            msg_signing_key
        )
        casper.functions.logout(logout_msg).transact({'from': tx_sender_addr})
    return logout_validator_via_signed_msg


@pytest.fixture
def logout_validator_via_unsigned_msg(casper, concise_casper, mk_logout_msg_unsigned):
    def logout_validator_via_unsigned_msg(validator_index, tx_sender_addr):
        logout_tx = mk_logout_msg_unsigned(validator_index, concise_casper.current_epoch())
        casper.functions.logout(logout_tx).transact({'from': tx_sender_addr})
    return logout_validator_via_unsigned_msg


@pytest.fixture
def deploy_validation_contract(w3, casper, mk_validation_code):
    def deploy_validation_contract(addr, valcode_type):
        tx_hash = w3.eth.sendTransaction({
            'to': '',
            'data': mk_validation_code(addr, valcode_type)
        })
        contract_address = w3.eth.getTransactionReceipt(tx_hash).contractAddress
        return contract_address
    return deploy_validation_contract


@pytest.fixture
def deposit_validator(w3, tester, casper, deploy_validation_contract):
    def deposit_validator(
            withdrawal_addr,
            validation_key,
            value,
            valcode_type="pure_ecrecover"):

        validation_addr = w3.eth.account.privateKeyToAccount(validation_key).address
        validation_contract_addr = deploy_validation_contract(validation_addr, valcode_type)

        casper.functions.deposit(
            validation_contract_addr,
            withdrawal_addr
        ).transact({
            'value': value
        })

        return casper.functions.validator_indexes(withdrawal_addr).call()
    return deposit_validator


# deposits privkey, value and steps forward two epochs
# to step dynasties forward to induct validator
# NOTE: This method only works when no deposits exist and chain insta-finalizes
#       If inducting a validator when desposits exists, use `deposit_validator` and
#       manually finalize
@pytest.fixture
def induct_validator(w3, tester, casper, deposit_validator, new_epoch):
    def induct_validator(
            withdrawal_addr,
            validation_key,
            value,
            valcode_type="pure_ecrecover"):

        validator_index = deposit_validator(
            withdrawal_addr,
            validation_key,
            value,
            valcode_type
        )
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
def induct_validators(tester, casper, deposit_validator, new_epoch):
    def induct_validators(accounts, validation_keys, values):
        start_index = casper.functions.next_validator_index().call()
        for account, key, value in zip(accounts, validation_keys, values):
            deposit_validator(account, key, value)
        new_epoch()  # justify
        new_epoch()  # finalize and increment dynasty
        new_epoch()  # finalize and increment dynasty
        return list(range(start_index, start_index + len(accounts)))
    return induct_validators


@pytest.fixture
def assert_failed():
    def assert_failed(function_to_test, exception):
        with pytest.raises(exception):
            function_to_test()
    return assert_failed


@pytest.fixture
def assert_tx_failed(base_tester):
    def assert_tx_failed(function_to_test, exception=eth_tester.exceptions.TransactionFailed):
        snapshot_id = base_tester.take_snapshot()
        with pytest.raises(exception):
            function_to_test()
        base_tester.revert_to_snapshot(snapshot_id)
    return assert_tx_failed
