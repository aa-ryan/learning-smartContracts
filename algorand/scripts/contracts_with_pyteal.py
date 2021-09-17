import base64
from algosdk import account
from algosdk.future.transaction import LogicSig, LogicSigTransaction, PaymentTxn
"""Simple bank for account contract where only a pre-defined receiver is able to
    withdraw funds from smart contract
"""

from pyteal import Addr, And, Global, Int, Mode, Txn, TxnType, compileTeal

BANK_ACCOUNT_FEE = 1000

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


