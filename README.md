# Casper

[![Build Status](https://travis-ci.org/ethereum/casper.svg?branch=master)](https://travis-ci.org/ethereum/casper)

## Casper Contract
Implements [Casper FFG](https://arxiv.org/abs/1710.09437), written in [Vyper](https://github.com/ethereum/vyper).

## Installation

For macOS, with [brew](https://brew.sh/) installed:

```bash
brew install pandoc # required for a python dependency
```

For all systems:

```bash
pip3 install -r requirements.txt
```

NOTE: pip3 is a version of pip using python version 3.
NOTE: we suggest using virtualenv to sandbox your setup.

## Tests

```bash
pytest tests
```

## Contribute

Join the conversation here: [https://gitter.im/ethereum/casper](https://gitter.im/ethereum/casper)
