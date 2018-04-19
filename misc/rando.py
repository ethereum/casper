from ethereum.tools import tester
from ethereum.utils import sha3, normalize_address

c = tester.Chain()
x = c.contract(open('rando.v.py').read(), language='vyper')
for i in range(10):
    x.deposit(sender=tester.keys[i], value=(i+1)*10**15)
    c.mine(1)

o = [0] * 10
for i in range(550):
    addr = normalize_address(x.random_select(sha3(str(i))))
    o[tester.accounts.index(addr)] += 1

for i, v in enumerate(o):
    ev = 10*(i+1)
    if not ev - 4*ev**0.5 < v < ev + 4*ev**0.5:
        raise Exception("More than four standard deviations away; something is wrong: %.2f %d %.2f" %
                        (ev - 4*ev**0.5, v, ev + 4*ev**0.5))
print(o)
