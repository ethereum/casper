# Casper

[![Build Status](https://travis-ci.org/ethereum/casper.svg?branch=master)](https://travis-ci.org/ethereum/casper)

## Resources

- [EIP-1011](https://github.com/ethereum/EIPs/blob/master/EIPS/eip-1011.md):
specifcation of the Casper the Friendly Finality Gadget (FFG) PoW/PoS consensus model.
- [VALIDATOR_GUIDE.md](https://github.com/ethereum/casper/blob/master/VALIDATOR_GUIDE.md):
information about implementing a Casper FFG validator.
- [Casper the Friendly Finality Gadget](https://arxiv.org/abs/1710.09437): 
  paper by Vitalik Buterin and Virgil Griffith introducing Casper FFG.

## Casper Contract
Implements [Casper FFG](https://arxiv.org/abs/1710.09437), written in [Vyper](https://github.com/ethereum/vyper).

## Installation

For macOS, with [brew](https://brew.sh/) installed:

```bash
brew install pandoc # required for a python dependency
```

For all systems:

```bash
pip3 install -r requirements.txt`
```

NOTE: pip3 is a version of pip using python version 3.
NOTE: we suggest using virtualenv to sandbox your setup.

## Tests

```bash
pytest tests
```

## Contribute

Join the conversation here: [https://gitter.im/ethereum/casper](https://gitter.im/ethereum/casper)
