from vyper import compiler, optimizer, compile_lll
from vyper.parser.parser_utils import LLLnode
from ethereum.utils import bytes_to_int


def generate_pure_ecrecover_as_LLL_source(address):
    return [
        'seq',
        ['calldatacopy', 0, 0, 128],
        ['call', 3000, 1, 0, 0, 128, 0, 32],
        ['mstore',
            0,
            ['eq',
                ['mload', 0],
                bytes_to_int(address)
            ]
        ],
        ['return', 0, 32],
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
        valcodes[key] = [
            'seq',
            expression,
            ['calldatacopy', 0, 0, 128],
            ['call', 3000, 1, 0, 0, 128, 0, 32],
            ['mstore',
                0,
                ['eq',
                    ['mload', 0],
                    bytes_to_int(address)
                ]
            ],
            ['return', 0, 32],
        ]
    return valcodes


def generate_unused_opcodes_as_evm_bytecode(address):
    valcodes = {}
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
    pure_ecrecover_bytecode = (
        "61003f56{start:02x}5060806000600037602060006080600060006001610bb8f15073"
        "{address}6000511460005260206000f35b61000461003f036100046000396100"
        "0461003f036000f3")
    for opcode in unused_opcodes:
        key = "impure_unused_bytecode_{}".format("{:02x}".format(opcode))
        formatted = pure_ecrecover_bytecode.format(
            start=opcode,
            address=address.hex())
        valcodes[key] = bytes.fromhex(formatted)
    return valcodes


def generate_all_valcodes(address):
    return {
        'pure_ecrecover': generate_pure_ecrecover_as_LLL_source(address),
        **generate_impure_opcodes_as_LLL_source(address),
        **generate_unused_opcodes_as_evm_bytecode
        (address),
    }


def all_known_valcode_types():
    return generate_all_valcodes(b'\x00').keys()


def compile_valcode_to_evm_bytecode(valcode_type, address):
    valcodes = generate_all_valcodes(address)
    valcode = valcodes[valcode_type]
    # We assume bytes are compiled evm code
    if type(valcode) is bytes:
        return valcode
    # We assume lists are uncompiled LLL seqs
    elif type(valcode) is list:
        deployable_lll = [
            'seq',
            ['return', [0],
                ['lll',
                    valcodes[valcode_type],
                    [0]
                ]
            ]
        ]
        lll_node = LLLnode.from_list(deployable_lll)
        optimized = optimizer.optimize(lll_node)
        assembly = compile_lll.compile_to_assembly(optimized)
        evm = compile_lll.assembly_to_evm(assembly)
        return evm
    # Any other types are unacceptable
    else:
        raise ValueError('Valcode must be of types list (uncompiled LLL), or '
                         'bytes (compiled bytecode). Given: '
                         '{}'.format(type(valcode)))
