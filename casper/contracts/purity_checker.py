## This Python source code hosts the Vyper LLL used for the purity checker.
## The purity checker scans a contract's bytecode to see if it uses any operations that rely on (external) mutable state.
## This code was ported from an original written in the deprecated Serpent: https://github.com/ethereum/research/blob/master/impurity/check_for_impurity.se

## The following are memory maps for each function:
# MEMORY MAP for `submit` method
# [320, 351]: addr, the input address, 32 bytes
# [352, 352+_EXTCODESIZE-1]: bytecode at addr, _EXTCODESIZE bytes
# [352+_EXTCODESIZE, 352+33*_EXTCODESIZE-32]: ops, array to hold processed opcodes, 32*_EXTCODESIZE bytes
# [352+33*_EXTCODESIZE, 352+65*_EXTCODESIZE-32]: pushargs, array to hold processed push arguments, 32*_EXTCODESIZE bytes
# [352+65*_EXTCODESIZE, 383+65*_EXTCODESIZE]: i, loop counter, 32 bytes

# MEMORY MAP for `check` method
# [320, 351]: addr, the input address, 32 bytes

from vyper import compile_lll, optimizer
from vyper.parser.parser import LLLnode

invalid_if_banned = ["if",
                     # sum([2**x for x in [0x31, 0x32, 0x33, 0x3a, 0x3b, 0x3c, 0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4a, 0x4b, 0x4c, 0x4d, 0x4e, 0x4f, 0x54, 0x55, 0xf0, 0xff]])
                     ["and", 57897811465722876096115075801844696845150819816717216876035649536196444422144,
                      ["exp", 2, "_c"]],
                     "invalid"]

is_push = ["and", ["le", 0x60, "_c"], ["le", "_c", 0x7f]]

def index_pushargs(index):
    return ["add", ["add", 352, ["mul", 33, "_EXTCODESIZE"]], ["mul", 32, index]]

handle_push = ["seq",
               ["mstore", index_pushargs("_op"), ["div", ["mload", ["add", ["add", 352, ["mload", "_i"]], 1]], ["exp", 256, ["sub", 0x7f, "_c"]]]],
               ["mstore", "_i", ["add", ["sub", "_c", 0x5f], ["mload", "_i"]]]] # there is an extra -1 in here to account for the increment of the repeat loop; -0x5e ~> -0x5f from the serpent code

is_some_call = ["or", ["eq", "_c", 0xf1],
                ["or", ["eq", "_c", 0xf2], ["eq", "_c", 0xf4]]]

def index_ops(index):
    return ["add", ["add", 352, "_EXTCODESIZE"], ["mul", 32, index]]

find_address = ["if", ["and", ["ge", "_op", 2],
                       ["and", ["ge", ["mload", index_ops(["sub", "_op", 1])], 0x60],
                        ["le", ["mload", index_ops(["sub", "_op", 1])], 0x7f]]],
                ["set", "_address_entry", ["sub", "_op", 2]],
                ["if",
                 ["and", ["ge", "_op", 4],
                  ["and", ["eq", ["mload", index_ops(["sub", "_op", 1])], 0x03],
                   ["and", ["eq",
                            ["mload", index_ops(["sub", "_op", 2])], 0x5a],
                    ["and", ["ge",
                             ["mload", index_ops(["sub", "_op", 3])], 0x60],
                     ["le",
                      ["mload", index_ops(["sub", "_op", 3])], 0x7f]]]]],
                 ["set", "_address_entry", ["sub", "_op", 4]],
                 ["if", ["and", ["ge", "_op", 2],
                         ["eq",
                          ["mload", index_ops(["sub", "_op", 1])], 0x5a]],
                  ["set", "_address_entry", ["sub", "_op", 2]],
                  ["if", ["and", ["ge", "_op", 2],
                          ["eq",
                           ["mload", index_ops(["sub", "_op", 1])], 0x90]],
                   ["set", "_address_entry", ["sub", "_op", 2]],
                   ["if", ["and", ["ge", "_op", 2],
                           ["and", ["ge",
                                    ["mload", index_ops(["sub", "_op", 1])], 0x80],
                            ["lt",
                             ["mload", index_ops(["sub", "_op", 1])], 0x90]]],
                    ["set", "_address_entry", ["sub", "_op", 2]],
                    "invalid"]]]]]

filter_address_usage = ["if", ["sload", ["add", ["sha3_32", 0], # self.approved_addrs
                                         ["mload", index_pushargs("_address_entry")]]],
                        ["seq"],
                        ["if", ["eq",
                                ["mload", index_ops("_address_entry")], 0x30],
                         ["seq"],
                         ["if", ["eq",
                                 ["mload", index_ops("_address_entry")], 0x60],
                          ["seq"],
                          "invalid"]]]

handle_some_call = ["with", "_address_entry", 0,
                    ["seq",
                     find_address,
                     filter_address_usage]]

dispatch_compound_sequences = ["if", is_push,
                               handle_push,
                               ["if", is_some_call,
                                handle_some_call]]

process_byte = ["seq",
                invalid_if_banned,
                dispatch_compound_sequences,
                ["mstore", ["add", ["add", 352, "_EXTCODESIZE"], ["mul", 32, "_op"]], "_c"],
                ["set", "_op", ["add", "_op", 1]]]

loop_body = ["if",
             ["ge", ["mload", "_i"], "_EXTCODESIZE"],
             "break",
             ["with", "_c", ["mod", ["mload", ["add", 352, ["sub", ["mload", "_i"], 31]]], 256],
              process_byte]]

purity_checker_lll = LLLnode.from_list(
    ["seq",
     ["return",
      0,
      ["lll",
       ["seq",
        ["mstore", 28, ["calldataload", 0]],
        ["mstore", 32, 1461501637330902918203684832716283019655932542976],
        ["mstore", 64, 170141183460469231731687303715884105727],
        ["mstore", 96, -170141183460469231731687303715884105728],
        ["mstore", 128, 1701411834604692317316873037158841057270000000000],
        ["mstore", 160, -1701411834604692317316873037158841057280000000000],
        ["if",
         ["eq", ["mload", 0], 2710585003], # submit
         ["seq",
          ["calldatacopy", 320, 4, 32],
          ["assert", ["iszero", "callvalue"]],
          ["uclamplt", ["calldataload", 4], ["mload", 32]], # checking address input
          # scan bytecode at address input
          ["with", "_EXTCODESIZE", ["extcodesize", ["mload", 320]], # addr
           ["if", ["eq", "_EXTCODESIZE", 0],
            "invalid", # ban accounts with no code
            ["seq",
             ["extcodecopy", ["mload", 320], 352, 0, "_EXTCODESIZE"],
             ["with", "_i", ["add", 352, ["mul", 65, "_EXTCODESIZE"]],
              ["with", "_op", 0,
               ["repeat", "_i", 0,
                115792089237316195423570985008687907853269984665640564039457584007913129639935,
                loop_body]]]]]],
          # approve the address `addr`
          ["sstore", ["add", ["sha3_32", 0], ["mload", 320]], 1],
          ["mstore", 0, 1],
          ["return", 0, 32],
          "stop"]],
        ["if",
         ["eq", ["mload", 0], 3258357672], # check
         ["seq",
          ["calldatacopy", 320, 4, 32],
          ["assert", ["iszero", "callvalue"]],
          ["uclamplt", ["calldataload", 4], ["mload", 32]], # checking address input
          ["mstore", 0, ["sload", ["add", ["sha3_32", 0], ["mload", 320]]]],
          ["return", 0, 32],
          "stop"]]],
       0]]])

def lll_to_evm(lll):
    return compile_lll.assembly_to_evm(compile_lll.compile_to_assembly(optimizer.optimize(lll)))

def purity_checker_data():
    return lll_to_evm(purity_checker_lll)

def purity_checker_data_hex():
    return '0x' + purity_checker_data().hex()

if __name__ == '__main__':
    import rlp
    from ethereum.transactions import Transaction

    # Borrowed from `/tests`
    VYPER_RLP_DECODER_TX_HEX = "0xf9035b808506fc23ac0083045f788080b903486103305660006109ac5260006109cc527f0100000000000000000000000000000000000000000000000000000000000000600035046109ec526000610a0c5260006109005260c06109ec51101515585760f86109ec51101561006e5760bf6109ec510336141558576001610a0c52610098565b60013560f76109ec51036020035260005160f66109ec510301361415585760f66109ec5103610a0c525b61022060016064818352015b36610a0c511015156100b557610291565b7f0100000000000000000000000000000000000000000000000000000000000000610a0c5135046109ec526109cc5160206109ac51026040015260016109ac51016109ac5260806109ec51101561013b5760016109cc5161044001526001610a0c516109cc5161046001376001610a0c5101610a0c5260216109cc51016109cc52610281565b60b86109ec5110156101d15760806109ec51036109cc51610440015260806109ec51036001610a0c51016109cc51610460013760816109ec5114156101ac5760807f01000000000000000000000000000000000000000000000000000000000000006001610a0c5101350410151558575b607f6109ec5103610a0c5101610a0c5260606109ec51036109cc51016109cc52610280565b60c06109ec51101561027d576001610a0c51013560b76109ec510360200352600051610a2c526038610a2c5110157f01000000000000000000000000000000000000000000000000000000000000006001610a0c5101350402155857610a2c516109cc516104400152610a2c5160b66109ec5103610a0c51016109cc516104600137610a2c5160b66109ec5103610a0c510101610a0c526020610a2c51016109cc51016109cc5261027f565bfe5b5b5b81516001018083528114156100a4575b5050601f6109ac511115155857602060206109ac5102016109005260206109005103610a0c5261022060016064818352015b6000610a0c5112156102d45761030a565b61090051610a0c516040015101610a0c51610900516104400301526020610a0c5103610a0c5281516001018083528114156102c3575b50506109cc516109005101610420526109cc5161090051016109005161044003f35b61000461033003610004600039610004610330036000f31b2d4f"  # NOQA

    rlp_tx = rlp.hex_decode(VYPER_RLP_DECODER_TX_HEX, Transaction)

    purity_checker_tx = Transaction(rlp_tx.nonce, rlp_tx.gasprice, 600000, '', rlp_tx.value, purity_checker_data(), rlp_tx.v, rlp_tx.r, rlp_tx.s)

    tx_hex = '0x' + rlp.encode(purity_checker_tx).hex()

    print('purity_checker_data_hex:', purity_checker_data_hex(), '\n')
    print('purity_checker_tx_hex:', tx_hex)
