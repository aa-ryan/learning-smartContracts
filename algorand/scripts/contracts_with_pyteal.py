
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
