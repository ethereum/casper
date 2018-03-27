# Casper

[![Build Status](https://travis-ci.org/ethereum/casper.svg?branch=master)](https://travis-ci.org/ethereum/casper)

This repository contains the stage 1 Casper contract & JSON-RPC daemon.

## Casper Contract
Implements the Casper [slashing conditions](https://medium.com/@VitalikButerin/minimal-slashing-conditions-20f0b500fc6c) and [dynamic validator sets](https://medium.com/@VitalikButerin/safety-under-dynamic-validator-sets-ef0c3bbdf9f6), written in [Vyper](https://github.com/ethereum/vyper).

## Casper Daemon
Implements the logic needed to be a Casper validator, communicating via the JSON-RPC interface.

---

For information regarding the Casper deployment,
[see the Casper v1 implementation guide ->](https://github.com/ethereum/research/wiki/Casper-Version-1-Implementation-Guide)
