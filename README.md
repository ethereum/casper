# Casper

[![](https://img.shields.io/badge/made%20by-Ethereum%20Foundation-blue.svg?style=flat-square)](http://ethereum.org)
[![Build Status](https://travis-ci.org/ethereum/casper.svg?branch=master)](https://travis-ci.org/ethereum/casper)
[![Casper](https://img.shields.io/badge/gitter-Casper-4AB495.svg)](https://gitter.im/ethereum/casper)
[![Casper scaling and protocol economics](https://img.shields.io/badge/gitter-Casper%20scaling%20and%20protocol%20economics-4AB495.svg)](https://gitter.im/ethereum/casper-scaling-and-protocol-economics)
[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat-square)](https://github.com/RichardLitt/standard-readme)

> Implements Casper FFG (the Friendly Finality Gadget), a Proof-of-Stake finality protocol that can be layered on any block proposal mechanism.

## Background

- Implements a [Casper FFG](https://arxiv.org/abs/1710.09437) smart contract, written in [Vyper](https://github.com/ethereum/vyper).
- See this [Casper the Friendly Finality Gadget](https://arxiv.org/abs/1710.09437) paper by Vitalik Buterin and Virgil Griffith introducing Casper FFG.
- [EIP-1011](https://github.com/ethereum/EIPs/blob/master/EIPS/eip-1011.md):
specification of the Casper the Friendly Finality Gadget (FFG) PoW/PoS consensus model.

## Installation

For macOS, with [brew](https://brew.sh/) installed:

```bash
brew install　pandoc # required for a python dependency
brew install leveldb
```

For all systems:

```bash
pip3 install -r requirements.txt
```

NOTE: pip3 is a version of pip using python version 3.
NOTE: we suggest using virtualenv to sandbox your setup.

## Usage

- [VALIDATOR_GUIDE.md](https://github.com/ethereum/casper/blob/master/VALIDATOR_GUIDE.md):
information about implementing a Casper FFG validator.

## Contribute

Feel free to ask questions in our [Gitter room](https://gitter.im/ethereum/casper) or open an [issue](https://github.com/ethereum/casper/issues) for feature requests or bug reports. Feel free to make a PR!

## License

[UNLICENSE](LICENSE)

## Tests

```bash
pytest tests
```
