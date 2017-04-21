import serpent
from ethereum import tester as t
import hash_ladder_signer as h
import binascii

s = t.state()

PROOFLEN = 7

signer = h.LamportSigner(b'\x54' * 32, PROOFLEN)

verifier_code = open('verify_hash_ladder_sig.se').read() \
    .replace('41fd19e4450fd5fa8499231552a2e967e95a6e5a8e6bb5de5523b9cbdfc559e7', signer.pub.hex())

verifier = s.contract(verifier_code)

s.send(t.k0, verifier, 0, b'\x81' * 32 + signer.sign(b'\x81' * 32, 9))
print('Verification successful')
print('Gas used: %d' % (s.state.receipts[-1].gas_used - s.state.receipts[-2].gas_used - s.last_tx.intrinsic_gas_used))
