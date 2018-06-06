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

from vyper.opcodes import opcodes

def find_opcode_hex(opcode):
    if opcode in opcodes:
        return opcodes[opcode][0]
    return opcode

banned_opcodes = map(find_opcode_hex,[
    'BALANCE',
    'ORIGIN',
    'CALLER',
    'GASPRICE',
    'EXTCODESIZE',
    'EXTCODECOPY',
    'BLOCKHASH',
    'COINBASE',
    'TIMESTAMP',
    'NUMBER',
    'DIFFICULTY',
    'GASLIMIT',
    0x46, # rest of the 0x40 opcode space
    0x47,
    0x48,
    0x49,
    0x4a,
    0x4b,
    0x4c,
    0x4d,
    0x4e,
    0x4f,
    'SLOAD',
    'SSTORE',
    'CREATE',
    'SELFDESTRUCT'
])

banned_opcodes_bitmask = sum([2**x for x in banned_opcodes])

invalid_if_banned = ["if",
                     ["and", banned_opcodes_bitmask, ["exp", 2, "_c"]],
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
