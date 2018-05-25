from web3 import Web3


def encode_int32(val):
    return Web3.toBytes(val).rjust(32, b'\x00')
