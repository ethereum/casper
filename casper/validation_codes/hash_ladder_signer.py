# Implements a version of https://gist.github.com/alexwebr/da8dd928002a236c4709

try:
    from Crypto.Hash import keccak
    sha3 = lambda x: keccak.new(digest_bits=256, data=x).digest()
except ImportError:
    import sha3 as _sha3
    sha3 = lambda x: _sha3.sha3_256(x).digest()

NUM_SUBKEYS = 26
DEPTH = 64

def iterate_hash(msg, n):
    for i in range(n):
        msg = sha3(msg)
    return msg

class LamportSigner():
    def __init__(self, key, depth):
        self.indexcount = 2**depth
        self.priv = key
        self.keys = []
        self.pubs = []
        for i in range(self.indexcount):
            subkeys = [sha3(key + bytes([i // 256, i % 256, j])) for j in range(NUM_SUBKEYS)]
            self.keys.append(subkeys)
            pubs = [iterate_hash(k, DEPTH) for k in subkeys]
            self.pubs.append(b''.join(pubs))
            if i % 256 == 255:
                print("Finished %d out of %d privkeys" % ((i + 1), self.indexcount))
        self.merkle_nodes = [0] * self.indexcount + [sha3(x) for x in self.pubs]
        for j in range(self.indexcount - 1, 0, -1):
            self.merkle_nodes[j] = sha3(self.merkle_nodes[j * 2] + self.merkle_nodes[j * 2 + 1])
            if j % 256 == 0:
                print("Building Merkle tree, %d values remaining" % j)
        self.pub = self.merkle_nodes[1]

    def merkle_prove_pubkey(self, index):
        adjusted_index = self.indexcount + index
        o = []
        while adjusted_index > 1:
            o.append(self.merkle_nodes[adjusted_index ^ 1])
            adjusted_index >>= 1
        return o

    def sign(self, msghash, index):
        assert isinstance(msghash, bytes)
        subkeys = self.keys[index]
        depths = [msghash[i] % DEPTH for i in range(NUM_SUBKEYS)]
        values = [iterate_hash(subkey, depth) for subkey, depth in zip(subkeys, depths)]
        return b''.join(values) + b''.join(self.merkle_prove_pubkey(index)) + bytes([index // 256, index % 256])
