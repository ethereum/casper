# Casper

This repository contains the stage 1 Casper contract & JSON-RPC daemon.

## Casper Contract
Casper contract written in Viper which implements the Casper [slashing conditions](https://medium.com/@VitalikButerin/safety-under-dynamic-validator-sets-ef0c3bbdf9f6) and [dynamic validator sets](https://medium.com/@VitalikButerin/minimal-slashing-conditions-20f0b500fc6c). 

For commit history see [`research/casper4`](https://github.com/ethereum/research/tree/master/casper4).

## Casper Daemon
Implements the logic needed to be a Casper validator, communicating via the JSON-RPC interface.

---

For information regarding the Casper deployment,
[see the Casper v1 implementation guide ->](https://github.com/ethereum/research/wiki/Casper-Version-1-Implementation-Guide)
