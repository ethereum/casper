# The purpose of this contract is to showcase how it actually
# is not all that complex to implement a scheme where anyone
# can deposit an arbitrary amount and validators can still be
# fairly pseudorandomly selected. It works by storing a binary
# tree where at each leaf of the tree it stores the total
# amount of ETH held by validators that are under that leaf.
# Random selection can then be done by climbing down the tree
# jumping left or right with probability weighted the value
# stored at each branch. Complexity of all operations (insert,
# delete, update, edit balance, read) is O(log(n)) though only
# insert is implemented so far. Implementing delete, update and
# a queue so that exited validators' slots can be reused should
# be fairly simple.

validator_table: public({bal: wei_value, addr: address}[65536])
next_validator_index: num
total_deposits: public(wei_value)

@payable
@public
def deposit():
    assert self.next_validator_index < 32768
    ind:num = 32768 + self.next_validator_index
    self.validator_table[ind].addr = msg.sender
    for i in range(15):
        self.validator_table[ind].bal += msg.value
        ind = ind / 2
    self.total_deposits += msg.value
    self.next_validator_index += 1

@public
@constant
def random_select(seed: bytes32) -> address:
    select_val:wei_value = as_wei_value(as_num128(num256_mod(as_num256(seed), as_num256(self.total_deposits))), wei)
    ind:num = 1
    for i in range(15):
        if select_val <= self.validator_table[ind * 2].bal:
            ind = ind * 2
        else:
            select_val -= self.validator_table[ind * 2].bal
            ind = ind * 2 + 1
    return self.validator_table[ind].addr
