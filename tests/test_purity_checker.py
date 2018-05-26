from eth_tester import EthereumTester
from eth_tester import PyEthereum21Backend

from ethereum.tools.tester import TransactionFailed

from vyper import compiler, compile_lll, optimizer
from vyper.parser.parser import LLLnode

false_hex = '0x' + '00' * 32
true_hex = '0x' + '0' * 63 + '1'

def purity_checker_data_hex():
    return "0x6103da56600035601c52740100000000000000000000000000000000000000006020526f7fffffffffffffffffffffffffffffff6040527fffffffffffffffffffffffffffffffff8000000000000000000000000000000060605274012a05f1fffffffffffffffffffffffffdabf41c006080527ffffffffffffffffffffffffed5fa0e000000000000000000000000000000000060a05263a1903eab600051141561038857602060046101403734156100b457600080fd5b60043560205181106100c557600080fd5b50610140513b60008114156100da57fe610367565b806000610160610140513c806060026101600160008160007fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff818352015b84845110151561012b5761036256610351565b610100601f8551036101600151068060020a7f80010000000000000000000000000000000000000030ffff1c0e000000000000161561016657fe5b607f811115816060111516156101a55780607f036101000a600186516101600101510484602002876021026101600101528451605f820301855261033d565b60f4811460f282141760f18214171561033c576000607f6001860360200288610160010151111560606001870360200289610160010151101516600286101516156101f5576002850390506102e2565b607f6003860360200288610160010151111560606003870360200289610160010151101516605a6002870360200289610160010151141660036001870360200289610160010151141660048610151615610254576004850390506102e1565b605a6001860360200288610160010151146002861015161561027b576002850390506102e0565b6090600186036020028861016001015114600286101516156102a2576002850390506102df565b609060018603602002886101600101511060806001870360200289610160010151101516600286101516156102dc576002850390506102de565bfe5b5b5b5b5b8060200287602102610160010151600060c052602060c0200154156103065761033a565b60308160200288610160010151141561031e57610339565b60608160200288610160010151141561033657610338565bfe5b5b5b505b5b808460200287610160010152600184019350505b5b8151600101808352811415610118575b505050505b50600161014051600060c052602060c0200155600160005261017c610160f3005b63c23697a860005114156103d557602060046101403734156103a957600080fd5b60043560205181106103ba57600080fd5b5061014051600060c052602060c020015460005260206000f3005b5b6100046103da036100046000396100046103da036000f3"  # NOQA

def lll_to_evm(lll):
    return compile_lll.assembly_to_evm(compile_lll.compile_to_assembly(optimizer.optimize(lll)))

# when submitted to purity checker, these should return True
success_cases = [
    """
@public
def foo(x:int128) -> int128:
    return x * 2
""",
"""
@public
def phooey(h:bytes32, v:uint256, r:uint256, s:uint256) -> address:
    return ecrecover(h, v, r, s)
"""
]

# when submitted to purity checker, these should return False
failed_cases = [
    """
horse: int128

@public
def foo() -> int128:
    return self.horse
""",
"""
@public
def foo() -> int128:
    return block.number
"""
]

ecrecover_lll_src = LLLnode.from_list([
    'seq',
    ['return', [0],
     ['lll',
      ['seq',
       ['calldatacopy', 0, 0, 128],
       ['call', 3000, 1, 0, 0, 128, 0, 32],
       ['mstore',
        0,
        ['eq',
         ['mload', 0],
         0]],
       ['return', 0, 32]],
      [0]]]])

def preapproved_call_to(addr):
    return LLLnode.from_list([
        'seq',
        ['return', [0],
         ['lll',
          ['seq',
           ['calldatacopy', 0, 0, 128],
           ['call', 3000, int(addr, 16), 0, 0, 128, 0, 32],
           ['return', 0, 32]],
         [0]]]])

def deploy_contract(t, acct, data):
    txn_hash = t.send_transaction({
        'from': acct,
        'gas': 600000,
        'data': data
    })
    txn_receipt = t.get_transaction_receipt(txn_hash)
    return txn_receipt['contract_address']

def deploy_minimal_contract(t, acct, should_fail=False):
    op = '01'
    if should_fail:
        op = '42'
        #                            preamble                       postamble for code load
    return deploy_contract(t, acct, '61000956' + '60026001' + op + '5b61000461000903610004600039610004610009036000f3')

def deploy_purity_checker(t, acct):
    return deploy_contract(t, acct, purity_checker_data_hex())

def call_purity_checker_check(t, purity_checker_addr, acct, addr):
    return t.call({
        'from': acct,
        'to': purity_checker_addr,
        'gas': 30000,
        'data': '0xc23697a8' + addr
    })

def call_purity_checker_submit(t, purity_checker_addr, acct, addr):
    return t.send_transaction({
        'from': acct,
        'to': purity_checker_addr,
        'gas': 300000,
        'data': '0xa1903eab' + addr
    })

def pad_addr(addr):
    return '0'*24 + addr[2:]

def call_purity_checker(method, t, purity_checker_addr, acct, addr):
    return {'check': call_purity_checker_check,
            'submit': call_purity_checker_submit}[method](t, purity_checker_addr, acct, pad_addr(addr))

def purity_checker_check(t, purity_checker_addr, acct, addr):
    return call_purity_checker('check', t, purity_checker_addr, acct, addr)

def purity_checker_submit(t, purity_checker_addr, acct, addr):
    return call_purity_checker('submit', t, purity_checker_addr, acct, addr)

def show(obj):
    print('>>', obj)

def run_test_for(t, purity_checker_addr, acct, addr, results, submit, should_fail):
    initial_check = purity_checker_check(t, purity_checker_addr, acct, addr)

    if results[0]:
        assert initial_check == true_hex
    else:
        assert initial_check == false_hex

    if submit:
        if should_fail:
            try:
                purity_checker_submit(t, purity_checker_addr, acct, addr)
            except TransactionFailed:
                pass
        else:
            purity_checker_submit(t, purity_checker_addr, acct, addr)

    next_check = purity_checker_check(t, purity_checker_addr, acct, addr)

    if results[1]:
        assert next_check == true_hex
    else:
        assert next_check == false_hex

def run_test(t, purity_checker_addr, acct, case):
    addr = case['addr']
    results = case['results']
    submit = case.get('submit', True)
    should_fail = case.get('should_fail', False)

    run_test_for(t, purity_checker_addr, acct, addr, results, submit, should_fail)

def test_purity_checker():
    t = EthereumTester(backend=PyEthereum21Backend())

    accounts = t.get_accounts()

    acct = accounts[0]
    external_acct = accounts[1]
    non_submitted_external_acct = accounts[2]

    purity_checker_addr = deploy_purity_checker(t, acct)

    # setup to call an already approved address
    some_pure_contract = deploy_minimal_contract(t, acct)
    purity_checker_submit(t, purity_checker_addr, acct, some_pure_contract)

    cases = [
        {
            'addr': external_acct,
            'results': [False, False],
            'should_fail': True,
            'name': 'external_contract'
        },
        {
            'addr': non_submitted_external_acct,
            'submit': False,
            'results': [False, False],
            'name': 'non_submitted_external_contract'
        },
        {
            'addr': deploy_minimal_contract(t, acct),
            'results': [False, True],
            'name': 'minimal_contract'
        },
        {
            'addr': deploy_minimal_contract(t, acct, should_fail=True),
            'results': [False, False],
            'should_fail': True,
            'name': 'minimal_contract'
        },
        {
            'addr': deploy_contract(t, acct, lll_to_evm(ecrecover_lll_src).hex()),
            'results': [False, True],
            'name': 'pure_ecrecover_contract'
        },
        {
            'addr': deploy_contract(t, acct, lll_to_evm(preapproved_call_to(some_pure_contract)).hex()),
            'results': [False, True],
            'name': 'calling_preapproved_contract'
        },
        {
            'addr': deploy_contract(t, acct, lll_to_evm(preapproved_call_to(external_acct)).hex()),
            'results': [False, False],
            'should_fail': True,
            'name': 'calling_unapproved_contract'
        },
        {
            'addr': deploy_contract(t, acct, compiler.compile(success_cases[0]).hex()),
            'results': [False, True],
            'name': success_cases[0]
        },
        {
            'addr': deploy_contract(t, acct, compiler.compile(success_cases[1]).hex()),
            'results': [False, True],
            'name': success_cases[0]
        },
        {
            'addr': deploy_contract(t, acct, compiler.compile(failed_cases[0]).hex()),
            'results': [False, False],
            'should_fail': True,
            'name': failed_cases[0]
        },
        {
            'addr': deploy_contract(t, acct, compiler.compile(failed_cases[1]).hex()),
            'results': [False, False],
            'should_fail': True,
            'name': failed_cases[1]
        }
    ]

    for case in cases:
        run_test(t, purity_checker_addr, acct, case)

if __name__ == '__main__':
    test_purity_checker()
