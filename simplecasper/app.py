# -*- coding: utf8 -*-
import os
import signal
import sys
from logging import StreamHandler
from uuid import uuid4

import click
import gevent
from gevent.event import Event

import ethereum.slogging as slogging
from casper_service import CasperService
from chain_service import ChainService
from accounts import AccountsService, Account
from db_service import DBService
from devp2p.app import BaseApp
from devp2p.discovery import NodeDiscovery
from devp2p.peermanager import PeerManager
from devp2p.service import BaseService
from ethereum.utils import encode_hex, decode_hex, sha3, privtopub
from simplecasper import __version__

slogging.PRINT_FORMAT = '%(asctime)s %(name)s:%(levelname).1s\t%(message)s'
log = slogging.get_logger('app')

services = [NodeDiscovery, PeerManager, DBService, AccountsService, ChainService, CasperService]

privkeys = [encode_hex(sha3(i)) for i in range(100, 200)]
pubkeys = [encode_hex(privtopub(decode_hex(k))[1:]) for k in privkeys]


class SimpleCasper(BaseApp):
    client_name = 'simplecasper'
    client_version = '%s/%s/%s' % (__version__, sys.platform,
                                   'py%d.%d.%d' % sys.version_info[:3])
    client_version_string = '%s/v%s' % (client_name, client_version)
    start_console = False
    default_config = dict(BaseApp.default_config)
    default_config['client_version_string'] = client_version_string
    default_config['post_app_start_callback'] = None
    script_globals = {}


@click.group(help='Welcome to {} {}'.format(SimpleCasper.client_name, SimpleCasper.client_version))
@click.option('-l', '--log_config', multiple=False, type=str, default=":info",
              help='log_config string: e.g. ":info,eth:debug', show_default=True)
@click.option('--log-file', type=click.Path(dir_okay=False, writable=True, resolve_path=True),
              help="Log to file instead of stderr.")
@click.option('--data-dir', '-d', multiple=False, type=str,
              help='data directory', default='data', show_default=True)
@click.option('--unlock', multiple=True, type=str,
              help='Unlock an account (prompts for password)')
@click.option('--password', type=click.File(), help='path to a password file')
@click.pass_context
def app(ctx, log_config, log_file, data_dir, unlock, password):
    slogging.configure(log_config, log_file=log_file)
    ctx.obj = {
        'log_config': log_config,
        'log_file': log_file,
        'config': {
            'node': {
                'data_dir': data_dir
            },
            'casper': {
                'network_id': 0,
                'validator_id': 0,
                'privkey': ''
            },
            'discovery': {
                'listen_host': '0.0.0.0',
                'listen_port': 20170,
                'bootstrap_nodes': [
                    'enode://%s@127.0.0.1:20170' % pubkeys[0]
                ]
            },
            'p2p': {
                'listen_host': '0.0.0.0',
                'listen_port': 20170,
                'max_peers': 4,
                'min_peers': 4
            }
        },
        'unlock': unlock,
        'password': password.read().rstrip() if password else None
    }


@app.command()
@click.argument('node_id', type=click.IntRange(0, 100))
@click.option('--console', is_flag=True, help='Immediately drop into interactive console.')
@click.option('--fake-account', is_flag=True, help='Use a fake account for testing purposes')
@click.pass_context
def run(ctx, node_id, console, fake_account):
    """Start the daemon"""
    config = ctx.obj['config']
    config['node']['privkey_hex'] = privkeys[node_id]
    config['discovery']['listen_port'] += node_id
    config['p2p']['listen_port'] += node_id
    log.info("starting", config=config)

    if config['node']['data_dir'] and not os.path.exists(config['node']['data_dir']):
        os.makedirs(config['node']['data_dir'])

    app = SimpleCasper(config)
    app.start_console = console

    for service in services:
        assert issubclass(service, BaseService)
        assert service.name not in app.services
        service.register_with_app(app)
        assert hasattr(app.services, service.name)
        # If this service is the account service, then attempt to unlock the coinbase
        if service is AccountsService:
            # If the fake_account flag is True, create a temparary fake account based on node_id
            if fake_account:
                account = Account.new('', decode_hex(privkeys[node_id]))
                app.services.accounts.add_account(account, store=False)
                continue
            unlock_accounts(ctx.obj['unlock'], app.services.accounts, password=ctx.obj['password'])
            try:
                app.services.accounts.coinbase
            except ValueError as e:
                log.fatal('invalid coinbase', coinbase=config.get('pow', {}).get('coinbase_hex'),
                          error=e.message)
                sys.exit()

    # start app
    log.info('starting')
    app.start()

    if ctx.obj['log_file']:
        log.info("Logging to file %s", ctx.obj['log_file'])
        # User requested file logging - remove stderr handler
        root_logger = slogging.getLogger()
        for hdl in root_logger.handlers:
            if isinstance(hdl, StreamHandler) and hdl.stream == sys.stderr:
                root_logger.removeHandler(hdl)
                break

    # wait for interrupt
    evt = Event()
    gevent.signal(signal.SIGQUIT, evt.set)
    gevent.signal(signal.SIGTERM, evt.set)
    evt.wait()

    # finally stop
    app.stop()


@app.group()
@click.pass_context
def account(ctx):
    """Manage accounts.
    For accounts to be accessible by pyethapp, their keys must be stored in the keystore directory.
    Its path can be configured through "accounts.keystore_dir".
    """
    app = SimpleCasper(ctx.obj['config'])
    ctx.obj['app'] = app
    AccountsService.register_with_app(app)
    unlock_accounts(ctx.obj['unlock'], app.services.accounts, password=ctx.obj['password'])


@account.command('new')
@click.option('--uuid', '-i', help='equip the account with a random UUID', is_flag=True)
@click.pass_context
def new_account(ctx, uuid):
    """Create a new account.

    This will generate a random private key and store it in encrypted form in the keystore
    directory. You are prompted for the password that is employed (if no password file is
    specified). If desired the private key can be associated with a random UUID (version 4) using
    the --uuid flag.
    """
    app = ctx.obj['app']
    if uuid:
        id_ = str(uuid4())
    else:
        id_ = None
    password = ctx.obj['password']
    if password is None:
        password = click.prompt('Password to encrypt private key', default='', hide_input=True,
                                confirmation_prompt=True, show_default=False)
    account = Account.new(password, uuid=id_)
    account.path = os.path.join(app.services.accounts.keystore_dir, account.address.encode('hex'))
    try:
        app.services.accounts.add_account(account)
    except IOError:
        click.echo('Could not write keystore file. Make sure you have write permission in the '
                   'configured directory and check the log for further information.')
        sys.exit(1)
    else:
        click.echo('Account creation successful')
        click.echo('  Address: ' + account.address.encode('hex'))
        click.echo('       Id: ' + str(account.uuid))


@account.command('list')
@click.pass_context
def list_accounts(ctx):
    """List accounts with addresses and ids.

    This prints a table of all accounts, numbered consecutively, along with their addresses and
    ids. Note that some accounts do not have an id, and some addresses might be hidden (i.e. are
    not present in the keystore file). In the latter case, you have to unlock the accounts (e.g.
    via "pyethapp --unlock <account> account list") to display the address anyway.
    """
    accounts = ctx.obj['app'].services.accounts
    if len(accounts) == 0:
        click.echo('no accounts found')
    else:
        fmt = '{i:>4} {address:<40} {id:<36} {locked:<1}'
        click.echo('     {address:<40} {id:<36} {locked}'.format(address='Address (if known)',
                                                                 id='Id (if any)',
                                                                 locked='Locked'))
        for i, account in enumerate(accounts):
            click.echo(fmt.format(i='#' + str(i + 1),
                                  address=(account.address or '').encode('hex'),
                                  id=account.uuid or '',
                                  locked='yes' if account.locked else 'no'))


@account.command('import')
@click.argument('f', type=click.File(), metavar='FILE')
@click.option('--uuid', '-i', help='equip the new account with a random UUID', is_flag=True)
@click.pass_context
def import_account(ctx, f, uuid):
    """Import a private key from FILE.

    FILE is the path to the file in which the private key is stored. The key is assumed to be hex
    encoded, surrounding whitespace is stripped. A new account is created for the private key, as
    if it was created with "pyethapp account new", and stored in the keystore directory. You will
    be prompted for a password to encrypt the key (if no password file is specified). If desired a
    random UUID (version 4) can be generated using the --uuid flag in order to identify the new
    account later.
    """
    app = ctx.obj['app']
    if uuid:
        id_ = str(uuid4())
    else:
        id_ = None
    privkey_hex = f.read()
    try:
        privkey = privkey_hex.strip().decode('hex')
    except TypeError:
        click.echo('Could not decode private key from file (should be hex encoded)')
        sys.exit(1)
    password = ctx.obj['password']
    if password is None:
        password = click.prompt('Password to encrypt private key', default='', hide_input=True,
                                confirmation_prompt=True, show_default=False)
    account = Account.new(password, privkey, uuid=id_)
    account.path = os.path.join(app.services.accounts.keystore_dir, account.address.encode('hex'))
    try:
        app.services.accounts.add_account(account)
    except IOError:
        click.echo('Could not write keystore file. Make sure you have write permission in the '
                   'configured directory and check the log for further information.')
        sys.exit(1)
    else:
        click.echo('Account creation successful')
        click.echo('  Address: ' + account.address.encode('hex'))
        click.echo('       Id: ' + str(account.uuid))


@account.command('update')
@click.argument('account', type=str)
@click.pass_context
def update_account(ctx, account):
    """
    Change the password of an account.

    ACCOUNT identifies the account: It can be one of the following: an address, a uuid, or a
    number corresponding to an entry in "pyethapp account list" (one based).

    "update" first prompts for the current password to unlock the account. Next, the new password
    must be entered.

    The password replacement procedure backups the original keystore file in the keystore
    directory, creates the new file, and finally deletes the backup. If something goes wrong, an
    attempt will be made to restore the keystore file from the backup. In the event that this does
    not work, it is possible to recover from the backup manually by simply renaming it. The backup
    shares the same name as the original file, but with an appended "~" plus a number if necessary
    to avoid name clashes.

    As this command tampers with your keystore directory, it is advisable to perform a manual
    backup in advance.

    If a password is provided via the "--password" option (on the "pyethapp" base command), it will
    be used to unlock the account, but not as the new password (as distinguished from
    "pyethapp account new").
    """
    app = ctx.obj['app']
    unlock_accounts([account], app.services.accounts, password=ctx.obj['password'])
    old_account = app.services.accounts.find(account)
    if old_account.locked:
        click.echo('Account needs to be unlocked in order to update its password')
        sys.exit(1)

    click.echo('Updating account')
    click.echo('Address: {}'.format(old_account.address.encode('hex')))
    click.echo('     Id: {}'.format(old_account.uuid))

    new_password = click.prompt('New password', default='', hide_input=True,
                                confirmation_prompt=True, show_default=False)

    try:
        app.services.accounts.update_account(old_account, new_password)
    except:
        click.echo('Account update failed. Make sure that the keystore file has been restored '
                   'correctly (e.g. with "pyethapp --unlock <acct> account list"). If not, look '
                   'for automatic backup files in the keystore directory (suffix "~" or '
                   '"~<number>"). Check the log for further information.')
        raise
    click.echo('Account update successful')


def unlock_accounts(account_ids, account_service, max_attempts=3, password=None):
    """Unlock a list of accounts, prompting for passwords one by one if not given.

    If a password is specified, it will be used to unlock all accounts. If not, the user is
    prompted for one password per account.

    If an account can not be identified or unlocked, an error message is logged and the program
    exits.

    :param accounts: a list of account identifiers accepted by :meth:`AccountsService.find`
    :param account_service: the account service managing the given accounts
    :param max_attempts: maximum number of attempts per account before the unlocking process is
                         aborted (>= 1), or `None` to allow an arbitrary number of tries
    :param password: optional password which will be used to unlock the accounts
    """
    accounts = []
    for account_id in account_ids:
        try:
            account = account_service.find(account_id)
        except KeyError:
            log.fatal('could not find account', identifier=account_id)
            sys.exit(1)
        accounts.append(account)

    if password is not None:
        for identifier, account in zip(account_ids, accounts):
            try:
                account.unlock(password)
            except ValueError:
                log.fatal('Could not unlock account with password from file',
                          account_id=identifier)
                sys.exit(1)
        return

    max_attempts_str = str(max_attempts) if max_attempts else 'oo'
    attempt_fmt = '(attempt {{attempt}}/{})'.format(max_attempts_str)
    first_attempt_fmt = 'Password for account {id} ' + attempt_fmt
    further_attempts_fmt = 'Wrong password. Please try again ' + attempt_fmt

    for identifier, account in zip(account_ids, accounts):
        attempt = 1
        pw = click.prompt(first_attempt_fmt.format(id=identifier, attempt=1), hide_input=True,
                          default='', show_default=False)
        while True:
            attempt += 1
            try:
                account.unlock(pw)
            except ValueError:
                if max_attempts and attempt > max_attempts:
                    log.fatal('Too many unlock attempts', attempts=attempt, account_id=identifier)
                    sys.exit(1)
                else:
                    pw = click.prompt(further_attempts_fmt.format(attempt=attempt),
                                      hide_input=True, default='', show_default=False)
            else:
                break
        assert not account.locked

if __name__ == '__main__':
    app()
