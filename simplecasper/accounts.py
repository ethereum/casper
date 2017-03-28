# Copied from https://github.com/ethereum/pyethapp/blob/e7717367387e506d8bed096bba1e553d11f0ac8b/pyethapp/accounts.py

import json
import os
import random
import shutil
from uuid import UUID
from devp2p.service import BaseService
from ethereum import keys
from ethereum.slogging import get_logger
from ethereum.utils import privtopub  # this is different  than the one used in devp2p.crypto
from ethereum.utils import sha3, is_string, decode_hex, remove_0x_head
log = get_logger('accounts')

DEFAULT_COINBASE = 'de0b295669a9fd93d5f28d9ec85e40f4cb697bae'.decode('hex')


def mk_privkey(seed):
    return sha3(seed)


def mk_random_privkey():
    k = hex(random.getrandbits(256))[2:-1].zfill(64)
    assert len(k) == 64
    return k.decode('hex')


class Account(object):

    """Represents an account.
    :ivar keystore: the key store as a dictionary (as decoded from json)
    :ivar locked: `True` if the account is locked and neither private nor public keys can be
                  accessed, otherwise `False`
    :ivar path: absolute path to the associated keystore file (`None` for in-memory accounts)
    """

    def __init__(self, keystore, password=None, path=None):
        self.keystore = keystore
        try:
            self._address = self.keystore['address'].decode('hex')
        except KeyError:
            self._address = None
        self.locked = True
        if password is not None:
            self.unlock(password)
        if path is not None:
            self.path = os.path.abspath(path)
        else:
            self.path = None

    @classmethod
    def new(cls, password, key=None, uuid=None, path=None):
        """Create a new account.
        Note that this creates the account in memory and does not store it on disk.
        :param password: the password used to encrypt the private key
        :param key: the private key, or `None` to generate a random one
        :param uuid: an optional id
        """
        if key is None:
            key = mk_random_privkey()
        keystore = keys.make_keystore_json(key, password)
        keystore['id'] = uuid
        return Account(keystore, password, path)

    @classmethod
    def load(cls, path, password=None):
        """Load an account from a keystore file.
        :param path: full path to the keyfile
        :param password: the password to decrypt the key file or `None` to leave it encrypted
        """
        with open(path) as f:
            keystore = json.load(f)
        if not keys.check_keystore_json(keystore):
            raise ValueError('Invalid keystore file')
        return Account(keystore, password, path=path)

    def dump(self, include_address=True, include_id=True):
        """Dump the keystore for later disk storage.
        The result inherits the entries `'crypto'` and `'version`' from `account.keystore`, and
        adds `'address'` and `'id'` in accordance with the parameters `'include_address'` and
        `'include_id`'.
        If address or id are not known, they are not added, even if requested.
        :param include_address: flag denoting if the address should be included or not
        :param include_id: flag denoting if the id should be included or not
        """
        d = {}
        d['crypto'] = self.keystore['crypto']
        d['version'] = self.keystore['version']
        if include_address and self.address is not None:
            d['address'] = self.address.encode('hex')
        if include_id and self.uuid is not None:
            d['id'] = self.uuid
        return json.dumps(d)

    def unlock(self, password):
        """Unlock the account with a password.
        If the account is already unlocked, nothing happens, even if the password is wrong.
        :raises: :exc:`ValueError` (originating in ethereum.keys) if the password is wrong (and the
                 account is locked)
        """
        if self.locked:
            self._privkey = keys.decode_keystore_json(self.keystore, password)
            self.locked = False
            self.address  # get address such that it stays accessible after a subsequent lock

    def lock(self):
        """Relock an unlocked account.
        This method sets `account.privkey` to `None` (unlike `account.address` which is preserved).
        After calling this method, both `account.privkey` and `account.pubkey` are `None.
        `account.address` stays unchanged, even if it has been derived from the private key.
        """
        self._privkey = None
        self.locked = True

    @property
    def privkey(self):
        """The account's private key or `None` if the account is locked"""
        if not self.locked:
            return self._privkey
        else:
            return None

    @property
    def pubkey(self):
        """The account's public key or `None` if the account is locked"""
        if not self.locked:
            return privtopub(self.privkey)
        else:
            return None

    @property
    def address(self):
        """The account's address or `None` if the address is not stored in the key file and cannot
        be reconstructed (because the account is locked)
        """
        if self._address:
            pass
        elif 'address' in self.keystore:
            self._address = self.keystore['address'].decode('hex')
        elif not self.locked:
            self._address = keys.privtoaddr(self.privkey)
        else:
            return None
        return self._address

    @property
    def uuid(self):
        """An optional unique identifier, formatted according to UUID version 4, or `None` if the
        account does not have an id
        """
        try:
            return self.keystore['id']
        except KeyError:
            return None

    @uuid.setter
    def uuid(self, value):
        """Set the UUID. Set it to `None` in order to remove it."""
        if value is not None:
            self.keystore['id'] = value
        elif 'id' in self.keystore:
            self.keystore.pop('id')

    def sign_tx(self, tx):
        """Sign a Transaction with the private key of this account.
        If the account is unlocked, this is equivalent to ``tx.sign(account.privkey)``.
        :param tx: the :class:`ethereum.transactions.Transaction` to sign
        :raises: :exc:`ValueError` if the account is locked
        """
        if self.privkey:
            log.info('signing tx', tx=tx, account=self)
            tx.sign(self.privkey)
        else:
            raise ValueError('Locked account cannot sign tx')

    def __repr__(self):
        if self.address is not None:
            address = self.address.encode('hex')
        else:
            address = '?'
        return '<Account(address={address}, id={id})>'.format(address=address, id=self.uuid)


class AccountsService(BaseService):

    """Service that manages accounts.
    At initialization, this service collects the accounts stored as key files in the keystore
    directory (config option `accounts.keystore_dir`) and below.
    To add more accounts, use :method:`add_account`.
    :ivar accounts: the :class:`Account`s managed by this service, sorted by the paths to their
                    keystore files
    :ivar keystore_dir: absolute path to the keystore directory
    """

    name = 'accounts'
    default_config = dict(accounts=dict(keystore_dir='keystore', must_include_coinbase=True))

    def __init__(self, app):
        super(AccountsService, self).__init__(app)
        self.keystore_dir = app.config['accounts']['keystore_dir']
        if not os.path.isabs(self.keystore_dir):
            self.keystore_dir = os.path.abspath(os.path.join(app.config['node']['data_dir'],
                                                             self.keystore_dir))
        assert os.path.isabs(self.keystore_dir)
        self.accounts = []
        if not os.path.exists(self.keystore_dir):
            log.warning('keystore directory does not exist', directory=self.keystore_dir)
        elif not os.path.isdir(self.keystore_dir):
            log.error('configured keystore directory is a file, not a directory',
                      directory=self.keystore_dir)
        else:
            # traverse file tree rooted at keystore_dir
            log.info('searching for key files', directory=self.keystore_dir)
            for dirpath, _, filenames in os.walk(self.keystore_dir):
                for filename in [os.path.join(dirpath, filename) for filename in filenames]:
                    try:
                        self.accounts.append(Account.load(filename))
                    except ValueError:
                        log.warning('invalid file skipped in keystore directory',
                                    path=filename)
        self.accounts.sort(key=lambda account: account.path)  # sort accounts by path
        if not self.accounts:
            log.warn('no accounts found')
        else:
            log.info('found account(s)', accounts=self.accounts)

    @property
    def coinbase(self):
        """Return the address that should be used as coinbase for new blocks.
        The coinbase address is given by the config field pow.coinbase_hex. If this does not exist
        or is `None`, the address of the first account is used instead. If there are no accounts,
        the coinbase is `DEFAULT_COINBASE`.
        :raises: :exc:`ValueError` if the coinbase is invalid (no string, wrong length) or there is
                 no account for it and the config flag `accounts.check_coinbase` is set (does not
                 apply to the default coinbase)
        """
        cb_hex = self.app.config.get('pow', {}).get('coinbase_hex')
        if cb_hex is None:
            if not self.accounts_with_address:
                return DEFAULT_COINBASE
            cb = self.accounts_with_address[0].address
        else:
            if not is_string(cb_hex):
                raise ValueError('coinbase must be string')
            try:
                cb = decode_hex(remove_0x_head(cb_hex))
            except (ValueError, TypeError):
                raise ValueError('invalid coinbase')
        if len(cb) != 20:
            raise ValueError('wrong coinbase length')
        if self.config['accounts']['must_include_coinbase']:
            if cb not in (acct.address for acct in self.accounts):
                raise ValueError('no account for coinbase')
        return cb

    def add_account(self, account, store=True, include_address=True, include_id=True):
        """Add an account.
        If `store` is true the account will be stored as a key file at the location given by
        `account.path`. If this is `None` a :exc:`ValueError` is raised. `include_address` and
        `include_id` determine if address and id should be removed for storage or not.
        This method will raise a :exc:`ValueError` if the new account has the same UUID as an
        account already known to the service. Note that address collisions do not result in an
        exception as those may slip through anyway for locked accounts with hidden addresses.
        """
        log.info('adding account', account=account)
        if account.uuid is not None:
            if len([acct for acct in self.accounts if acct.uuid == account.uuid]) > 0:
                log.error('could not add account (UUID collision)', uuid=account.uuid)
                raise ValueError('Could not add account (UUID collision)')
        if store:
            if account.path is None:
                raise ValueError('Cannot store account without path')
            assert os.path.isabs(account.path), account.path
            if os.path.exists(account.path):
                log.error('File does already exist', path=account.path)
                raise IOError('File does already exist')
            assert account.path not in [acct.path for acct in self.accounts]
            try:
                directory = os.path.dirname(account.path)
                if not os.path.exists(directory):
                    os.makedirs(directory)
                with open(account.path, 'w') as f:
                    f.write(account.dump(include_address, include_id))
            except IOError as e:
                log.error('Could not write to file', path=account.path, message=e.strerror,
                          errno=e.errno)
                raise
        self.accounts.append(account)
        self.accounts.sort(key=lambda account: account.path)

    def update_account(self, account, new_password, include_address=True, include_id=True):
        """Replace the password of an account.
        The update is carried out in three steps:
        1) the old keystore file is renamed
        2) the new keystore file is created at the previous location of the old keystore file
        3) the old keystore file is removed
        In this way, at least one of the keystore files exists on disk at any time and can be
        recovered if the process is interrupted.
        :param account: the :class:`Account` which must be unlocked, stored on disk and included in
                        :attr:`AccountsService.accounts`.
        :param include_address: forwarded to :meth:`add_account` during step 2
        :param include_id: forwarded to :meth:`add_account` during step 2
        :raises: :exc:`ValueError` if the account is locked, if it is not added to the account
                 manager, or if it is not stored
        """
        if account not in self.accounts:
            raise ValueError('Account not managed by account service')
        if account.locked:
            raise ValueError('Cannot update locked account')
        if account.path is None:
            raise ValueError('Account not stored on disk')
        assert os.path.isabs(account.path)

        # create new account
        log.debug('creating new account')
        new_account = Account.new(new_password, key=account.privkey, uuid=account.uuid)
        new_account.path = account.path

        # generate unique path and move old keystore file there
        backup_path = account.path + '~'
        i = 1
        while os.path.exists(backup_path):
            backup_path = backup_path[:backup_path.rfind('~') + 1] + str(i)
            i += 1
        assert not os.path.exists(backup_path)
        log.info('moving old keystore file to backup location', **{'from': account.path,
                                                                   'to': backup_path})
        try:
            shutil.move(account.path, backup_path)
        except:
            log.error('could not backup keystore, stopping account update',
                      **{'from': account.path, 'to': backup_path})
            raise

        assert os.path.exists(backup_path)
        assert not os.path.exists(new_account.path)
        account.path = backup_path

        # remove old account from manager (not from disk yet) and add new account
        self.accounts.remove(account)
        assert account not in self.accounts
        try:
            self.add_account(new_account, include_address, include_id)
        except:
            log.error('adding new account failed, recovering from backup')
            shutil.move(backup_path, new_account.path)
            self.accounts.append(account)
            self.accounts.sort(key=lambda account: account.path)
            raise

        assert os.path.exists(new_account.path)
        assert new_account in self.accounts

        # everything was successful (we are still here), so delete old keystore file
        log.info('deleting backup of old keystore', path=backup_path)
        try:
            os.remove(backup_path)
        except:
            log.error('failed to delete no longer needed backup of old keystore',
                      path=account.path)
            raise

        # set members of account to values of new_account
        account.keystore = new_account.keystore
        account.path = new_account.path
        assert account.__dict__ == new_account.__dict__
        # replace new_account by old account in account list
        self.accounts.append(account)
        self.accounts.remove(new_account)
        self.accounts.sort(key=lambda account: account.path)
        log.debug('account update successful')

    @property
    def accounts_with_address(self):
        """Return a list of accounts whose address is known."""
        return [account for account in self if account.address]

    @property
    def unlocked_accounts(self):
        """Return a list of all unlocked accounts."""
        return [account for account in self if not account.locked]

    def find(self, identifier):
        """Find an account by either its address, its id or its index as string.
        Example identifiers:
        - '9c0e0240776cfbe6fa1eb37e57721e1a88a563d1' (address)
        - '0x9c0e0240776cfbe6fa1eb37e57721e1a88a563d1' (address with 0x prefix)
        - '01dd527b-f4a5-4b3c-9abb-6a8e7cd6722f' (UUID)
        - '3' (index)
        :param identifier: the accounts hex encoded, case insensitive address (with optional 0x
                           prefix), its UUID or its index (as string, >= 1) in
                           `account_service.accounts`
        :raises: :exc:`ValueError` if the identifier could not be interpreted
        :raises: :exc:`KeyError` if the identified account is not known to the account_service
        """
        try:
            uuid = UUID(identifier)
        except ValueError:
            pass
        else:
            return self.get_by_id(str(uuid))

        try:
            index = int(identifier, 10)
        except ValueError:
            pass
        else:
            if index <= 0:
                raise ValueError('Index must be 1 or greater')
            try:
                return self.accounts[index - 1]
            except IndexError as e:
                raise KeyError(e.message)

        if identifier[:2] == '0x':
            identifier = identifier[2:]
        try:
            address = identifier.decode('hex')
        except TypeError:
            success = False
        else:
            if len(address) != 20:
                success = False
            else:
                return self[address]

        assert not success
        raise ValueError('Could not interpret account identifier')

    def get_by_id(self, id):
        """Return the account with a given id.
        Note that accounts are not required to have an id.
        :raises: `KeyError` if no matching account can be found
        """
        accts = [acct for acct in self.accounts if UUID(acct.uuid) == UUID(id)]
        assert len(accts) <= 1
        if len(accts) == 0:
            raise KeyError('account with id {} unknown'.format(id))
        elif len(accts) > 1:
            log.warning('multiple accounts with same UUID found', uuid=id)
        return accts[0]

    def get_by_address(self, address):
        """Get an account by its address.
        Note that even if an account with the given address exists, it might not be found if it is
        locked. Also, multiple accounts with the same address may exist, in which case the first
        one is returned (and a warning is logged).
        :raises: `KeyError` if no matching account can be found
        """
        assert len(address) == 20
        accounts = [account for account in self.accounts if account.address == address]
        if len(accounts) == 0:
            raise KeyError('account not found by address', address=address.encode('hex'))
        elif len(accounts) > 1:
            log.warning('multiple accounts with same address found', address=address.encode('hex'))
        return accounts[0]

    def sign_tx(self, address, tx):
        self.get_by_address(address).sign_tx(tx)

    def propose_path(self, address):
        return os.path.join(self.keystore_dir, address.encode('hex'))

    def __contains__(self, address):
        assert len(address) == 20
        return address in [a.address for a in self.accounts]

    def __getitem__(self, address_or_idx):
        if isinstance(address_or_idx, bytes):
            address = address_or_idx
            assert len(address) == 20
            for a in self.accounts:
                if a.address == address:
                    return a
            raise KeyError
        else:
            assert isinstance(address_or_idx, int)
            return self.accounts[address_or_idx]

    def __iter__(self):
        return iter(self.accounts)

    def __len__(self):
        return len(self.accounts)


"""
--import-key = key.json
--unlock <password dialog>
--password  passwordfile
--newkey    <password dialog>
"""
