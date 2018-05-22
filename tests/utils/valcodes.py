from vyper import optimizer, compile_lll
from vyper.parser.parser_utils import LLLnode
from web3 import Web3


# We must know a pure opcode so we can do control tests
PURE_OPCODE_HEX = 0x59
PURE_EXPRESSION_LLL = ['msize']

# Expensive opcode for testing gas limits
ECRECOVER_LLL = ['call', 3000, 1, 0, 0, 128, 0, 32]
ECRECOVER_GASCOST = 3000


def generate_pure_ecrecover_LLL_source(address):
    return [
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
                            Web3.toInt(hexstr=address)]],
                    ['return', 0, 32]],
                [0]]]
    ]


def format_LLL_source(address, expression):
    return [
        'seq',
        ['return', [0],
            ['lll',
                ['seq',
                    expression,  # impure_expression goes here
                    ['calldatacopy', 0, 0, 128],
                    ['call', 3000, 1, 0, 0, 128, 0, 32],
                    ['mstore',
                        0,
                        ['eq',
                            ['mload', 0],
                            Web3.toInt(hexstr=address)]],
                    ['return', 0, 32]],
                [0]]]
    ]


def generate_impure_opcodes_as_LLL_source(address):
    impure_expressions = [
        ['balance', 1337],
        ['origin'],
        ['caller'],
        ['gasprice'],
        ['extcodesize', 1337],
        ['extcodecopy', 1337, 0, 0, 1],
        ['blockhash', 1337],
        ['coinbase'],
        ['timestamp'],
        ['number'],
        ['difficulty'],
        ['gaslimit'],
        ['sload', 0],
        ['sstore', 1, 1],
        ['create', 0, 0, 1],
        ['selfdestruct', 1337],
    ]
    valcodes = {}
    for expression in impure_expressions:
        key = "impure_{}".format(expression[0])
        valcodes[key] = format_LLL_source(address, expression)
    return valcodes


def format_ecrecover_bytecode(address, opcode):
    pure_ecrecover_bytecode = (
        "61003f56{start:02x}5060806000600037602060006080600060006001610"
        "bb8f15073{address}6000511460005260206000f35b61000461003f036100"
        "0460003961000461003f036000f3"
    )
    return bytes.fromhex(
        pure_ecrecover_bytecode.format(
            start=opcode,
            address=address[2:]
        )
    )


def generate_unused_opcodes_as_evm_bytecode(address):
    unused_opcodes = [
        0x46,
        0x47,
        0x48,
        0x49,
        0x4a,
        0x4b,
        0x4c,
        0x4d,
        0x4e,
        0x4f,
    ]
    valcodes = {}
    for opcode in unused_opcodes:
        key = "impure_unused_bytecode_{}".format("{:02x}".format(opcode))
        valcodes[key] = format_ecrecover_bytecode(address, opcode)
    return valcodes


def generate_all_valcodes(address):
    return {
        'pure_ecrecover': generate_pure_ecrecover_LLL_source(address),
        'pure_LLL_source_as_control': format_LLL_source(
            address, PURE_EXPRESSION_LLL),
        'pure_bytecode_as_control': format_ecrecover_bytecode(
            address, PURE_OPCODE_HEX),
        'pure_greater_than_200k_gas': format_LLL_source(
            address, ['seq'] + [ECRECOVER_LLL] * int(2e5 / ECRECOVER_GASCOST)),
        'pure_between_100k-200k_gas': format_LLL_source(
            address, ['seq'] + [ECRECOVER_LLL] * int(1e5 / ECRECOVER_GASCOST)),
        **generate_impure_opcodes_as_LLL_source(address),
        **generate_unused_opcodes_as_evm_bytecode(address),
    }


def all_known_valcode_types():
    return generate_all_valcodes('0x00').keys()


def compile_valcode_to_evm_bytecode(valcode_type, address):
    valcodes = generate_all_valcodes(address)
    valcode = valcodes[valcode_type]
    # We assume bytes are compiled evm code
    if type(valcode) is bytes:
        return valcode
    # We assume lists are uncompiled LLL seqs
    elif type(valcode) is list:
        lll_node = LLLnode.from_list(valcode)
        optimized = optimizer.optimize(lll_node)
        assembly = compile_lll.compile_to_assembly(optimized)
        evm = compile_lll.assembly_to_evm(assembly)
        return evm
    # Any other types are unacceptable
    else:
        raise ValueError('Valcode must be of types list (uncompiled LLL), or '
                         'bytes (compiled bytecode). Given: '
                         '{}'.format(type(valcode)))
