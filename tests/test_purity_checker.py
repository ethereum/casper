import pytest

from eth_tester.exceptions import TransactionFailed

from vyper import compiler, compile_lll, optimizer
from vyper.parser.parser import LLLnode

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
""",
"""
@public
def foo() -> int128:
    return msg.gas
"""]

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

def deploy_contract(w3, acct, data):
    txn_hash = w3.eth.sendTransaction({
        'from': acct,
        'gas': 400000,
        'data': data
    })
    txn_receipt = w3.eth.getTransactionReceipt(txn_hash)
    return txn_receipt.contractAddress

def deploy_minimal_contract(w3, acct, should_fail=False):
    op = '01'
    if should_fail:
        op = '42'
    #                                preamble                       postamble for code load
    return deploy_contract(w3, acct, '61000956' + '60026001' + op + '5b61000461000903610004600039610004610009036000f3')

def run_test_for(purity_checker, addr, results, submit, should_fail):
    initial_check = purity_checker.functions.check(addr).call()

    assert results[0] == initial_check

    if submit:
        if should_fail:
            with pytest.raises(TransactionFailed):
                purity_checker.functions.submit(addr).call()
        else:
            purity_checker.functions.submit(addr).transact()

    next_check = purity_checker.functions.check(addr).call()

    assert results[1] == next_check

def run_test(purity_checker, case):
    addr = case['addr']
    results = case['results']
    submit = case.get('submit', True)
    should_fail = case.get('should_fail', False)

    run_test_for(purity_checker, addr, results, submit, should_fail)

## NOTE: there is some dependency ordering with pytest fixtures; `casper` is not used here
def test_purity_checker(casper,
                        w3,
                        funded_accounts,
                        purity_checker):
    acct = funded_accounts[0]
    external_acct = funded_accounts[1]
    non_submitted_external_acct = funded_accounts[2]

    # setup to call an already approved address
    some_pure_contract = deploy_minimal_contract(w3, acct)
    purity_checker.functions.submit(some_pure_contract).transact()

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
            'addr': deploy_minimal_contract(w3, acct),
            'results': [False, True],
            'name': 'minimal_contract'
        },
        {
            'addr': deploy_minimal_contract(w3, acct, should_fail=True),
            'results': [False, False],
            'should_fail': True,
            'name': 'minimal_contract'
        },
        {
            'addr': deploy_contract(w3, acct, lll_to_evm(ecrecover_lll_src).hex()),
            'results': [False, True],
            'name': 'pure_ecrecover_contract'
        },
        {
            'addr': deploy_contract(w3, acct, lll_to_evm(preapproved_call_to(some_pure_contract)).hex()),
            'results': [False, True],
            'name': 'calling_preapproved_contract'
        },
        {
            'addr': deploy_contract(w3, acct, lll_to_evm(preapproved_call_to(external_acct)).hex()),
            'results': [False, False],
            'should_fail': True,
            'name': 'calling_unapproved_contract'
        },
        {
            'addr': deploy_contract(w3, acct, compiler.compile(success_cases[0]).hex()),
            'results': [False, True],
            'name': success_cases[0]
        },
        {
            'addr': deploy_contract(w3, acct, compiler.compile(success_cases[1]).hex()),
            'results': [False, True],
            'name': success_cases[0]
        },
        {
            'addr': deploy_contract(w3, acct, compiler.compile(failed_cases[0]).hex()),
            'results': [False, False],
            'should_fail': True,
            'name': failed_cases[0]
        },
        {
            'addr': deploy_contract(w3, acct, compiler.compile(failed_cases[1]).hex()),
            'results': [False, False],
            'should_fail': True,
            'name': failed_cases[1]
        },
        {
            'addr': deploy_contract(w3, acct, compiler.compile(failed_cases[2]).hex()),
            'results': [False, False],
            'should_fail': True,
            'name': failed_cases[2]
        }
    ]

    for case in cases:
        run_test(purity_checker, case)
