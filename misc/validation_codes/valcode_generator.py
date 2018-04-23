"""
This script generates the `valcodes.txt` file, which contains a
dict mapping strings to bytecodes. These bytecodes are
signature validation contracts and are used in
"tests/test_valcode_purity.py" for testing if the casper contract
will reject impure contracts.

Note: requirements.txt does not currently specify for serpent
to be installed. You can install it with:

`$ pip install git+https://github.com/ethereum/serpent.git`
"""
import pprint
import serpent
from ethereum import utils

pure = '''
~calldatacopy(0, 0, 128)
~call(3000, 1, 0, 0, 128, 0, 32)
return(~mload(0) == {})
'''

sload = '''
~sload(0)
~calldatacopy(0, 0, 128)
~call(3000, 1, 0, 0, 128, 0, 32)
return(~mload(0) == {})
'''

sstore = '''
~calldatacopy(0, 0, 128)
~call(3000, 1, 0, 0, 128, 0, 32)
~sstore(1, 1)
return(~mload(0) == {})
'''

codes = dict(
    pure=pure,
    sload=sload,
    sstore=sstore,
)


def compile(code):
    return serpent.compile(code)


def get_compiled_codes():
    addr = utils.privtoaddr(1337)
    output = dict()
    for name, code in codes.items():
        # Compile the serpent code
        compiled = compile(
            code.format(utils.checksum_encode(addr))
        )
        # Replace the address in the compiled code
        compiled = compiled.replace(addr, b'{address}')
        output[name] = compiled
    return output


# Dump the dict (as a string) into the valcodes file
with open('valcodes.txt', 'w') as f:
    compiled_codes = get_compiled_codes()
    output = pprint.pformat(compiled_codes)
    f.write(output)
