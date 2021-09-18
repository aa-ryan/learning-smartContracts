import base64
import os
import subprocess
import pty
from pathlib import Path
from algosdk import account, mnemonic
from algosdk.future.transaction import LogicSig, LogicSigTransaction, PaymentTxn
from algosdk.v2client import algod, indexer
"""Simple bank for account contract where only a pre-defined receiver is able to
    withdraw funds from smart contract
"""

from pyteal import Addr, And, Global, Int, Mode, Txn, TxnType, compileTeal

BANK_ACCOUNT_FEE = 1000
INDEXER_TIMEOUT = 10  # 61 for devMode

def bank_for_account(receiver):
    """Only allow receiver to withdraw funds from this contract account.
    Args:
        receiver (str): Base 32 Algorand address of the receiver.
    """

    is_payment = Txn.type_enum() == TxnType.Payment
    is_single_tx = Global.group_size() == Int(1)
    is_correct_receiver = Txn.receiver() == Addr(receiver)
    no_close_out_addr = Txn.close_remainder_to() == Global.zero_address()
    no_rekey_addr = Txn.rekey_to() == Global.zero_address()
    acceptable_fee = Txn.fee() <= Int(BANK_ACCOUNT_FEE)

    return And(
        is_payment,
        is_single_tx,
        is_correct_receiver,
        no_close_out_addr,
        no_rekey_addr,
        acceptable_fee,
    )


"""Above PyTeal code is then compiled into TEAL byte-code using PyTeal's `compileTeal`
    function and a signed logic signature is created from the compiled source
"""

def setup_bank_contract(**kwargs):
    """Initialize and return bank contract for provided receiver."""
    receiver = kwargs.pop("receiver", add_standalone_account()[1])

    teal_source = compileTeal(
        bank_for_account(receiver),
        mode = Mode.Signature,
        version = 3,
    )
    logic_sig = logic_signature(teal_source)
    escrow_address = logic_sig.address()
    fund_account(escrow_address)  # provide some funds to escrow account
    return logic_sig, escrow_address, receiver

def create_bank_transaction(logic_sig, escrow_address, receiver, amount, fee=1000):
    """Create a bank transaction with provided amount."""
    params = suggested_params()
    params.fee = fee
    params.flat_fee = True
    payment_transaction = create_payment_transaction(
        escrow_address, params, receiver, amount
    )
    transaction_id = process_logic_sig_transaction(logic_sig, payment_transaction)
    return transaction_id

def create_payment_transaction(escrow_address, params, receiver, amount):
    """Create and erturn payment transaction from provided arguments"""
    return PaymentTxn(escrow_address, params, receiver, amount)

def process_logic_sig_transaction(logic_sig, payment_transaction):
    """Create logic signature transaction and send it to the network"""
    client = _algod_client()
    logic_sig_transaction = LogicSigTransaction(payment_transaction, logic_sig)
    transaction_id = client.send_transaction(logic_sig_transaction)
    _wait_for_confirmation(client, transaction_id, 4)
    return transaction_id

def _compile_source(source):
    """Compile and return teal binary code"""
    compile_reponse = _algod_client().compile(source)
    return base64.b64decode(compile_reponse["result"])

def logic_signature(teal_source):
    """Create and return logic signature for provided teal_source"""
    compiled_binary = _compile_source(teal_source)
    return LogicSig(compiled_binary)

## HELPER function

# Creating
def add_standalone_account():
    """Creata standalone account and return two-tuple of it's private key and address."""
    private_key, address = account.generate_account()
    return private_key, address

def fund_account(address, initial_funds=1000000000):
    """Fund Provided `address` with `initial_funds` amount of microAlgos"""
    initial_funds_address = _initial_funds_address()
    if initial_funds_address is None:
        raise Exception("Initial funds weren't transferred")
    _add_transaction(
        initial_funds_address,
        address,
        _cli_passphrase_for_account(initial_funds_address),
        initial_funds,
        "Initial funds,"
    )

# Clients

def _algod_client():
    """Instantiate and return Algod client object."""
    algod_address = "http://localhost:4001"
    algod_token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    return algod.AlgodClient(algod_token, algod_address)


def _indexer_client():
    """Instantiate and return Indexer client object."""
    indexer_address = "http://localhost:8980"
    indexer_token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    return indexer.IndexerClient(indexer_token, indexer_address)



# Retrieving

def _initial_funds_address():
    """Get the address of initially created account having enough funds.
    Such an account is used to transfer initial funds for the accounts
    created in this tutorial
    """
    return next(
        (
            account.get("address")
            for account in _indexer_client().accounts().get("accounts", [{}, {}])
            if account.get("created-at-round") == 0
            and account.get("status") == "Offline" # online for dev mode
        ),
        None,
    )

def account_balance(address):
    """Retrun funds balance of account having provided address."""
    account_info = _algod_client().account_info(address)
    return account_info.get("amount")

## Sandbox

def _cli_passphrase_for_account(address):
    """Return passphrase for provided address."""
    process = call_sandbox_command("goal", "account", "export", "-a", address)

    if process.stderr:
        raise RuntimeError(process.stderr.decode("utf8"))

    passphrase = ""
    parts = process.stdout.decode("utf8").split('"')
    if len(parts) > 1:
        passphrase = parts[1]
    if passphrase == "":
        raise ValueError(
            "Can't retrieve passphrase from the address: %s\nOutput: %s"
            % (address, process.stdout.decode("utf8"))
        )
    return passphrase


def _sandbox_directory():
    """Return full path to Algorand's sandbox executable.
    The location of sandbox directory is retrieved either from the SANDBOX_DIR
    environment variable or if it's not set then the location of sandbox directory
    is implied to be the sibling of this Django project in the directory tree.
    """
    return os.environ.get("SANDBOX_DIR") or str(
        Path(__file__).resolve().parent.parent / "sandbox"
    )


def _sandbox_executable():
    """Return full path to Algorand's sandbox executable."""
    return _sandbox_directory() + "/sandbox"


def call_sandbox_command(*args):
    """Call and return sandbox command composed from provided arguments."""
    return subprocess.run(
        [_sandbox_executable(), *args], stdin=pty.openpty()[1], capture_output=True
    )

# Transactions

def _add_transaction(sender, receiver, passphrase, amount, note):
    """Create and sign transaction from provided arguments.
    Returned non-empty tuple carries field where error was raised and description.
    If the first item is None then the error is non-field/integration error.
    Returned two-tuple of empty strings marks successful transaction.
    """
    client = _algod_client()
    params = client.suggested_params()
    unsigned_txn = PaymentTxn(sender, params, receiver, amount, None, note.encode())
    signed_txn = unsigned_txn.sign(mnemonic.to_private_key(passphrase))
    transaction_id = client.send_transaction(signed_txn)
    _wait_for_confirmation(client, transaction_id, 4)
    return transaction_id


def _wait_for_confirmation(client, transaction_id, timeout):
    """
    Wait until the transaction is confirmed or rejected, or until 'timeout'
    number of rounds have passed.
    Args:
        transaction_id (str): the transaction to wait for
        timeout (int): maximum number of rounds to wait
    Returns:
        dict: pending transaction information, or throws an error if the transaction
            is not confirmed or rejected in the next timeout rounds
    """
    start_round = client.status()["last-round"] + 1
    current_round = start_round

    while current_round < start_round + timeout:
        try:
            pending_txn = client.pending_transaction_info(transaction_id)
        except Exception:
            return
        if pending_txn.get("confirmed-round", 0) > 0:
            return pending_txn
        elif pending_txn["pool-error"]:
            raise Exception("pool error: {}".format(pending_txn["pool-error"]))
        client.status_after_block(current_round)
        current_round += 1
    raise Exception(
        "pending tx not found in timeout rounds, timeout value = : {}".format(timeout)
    )


def suggested_params():
    """Return the suggested params from the algod client."""
    return _algod_client().suggested_params()

