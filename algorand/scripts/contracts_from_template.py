from algosdk import template
from algosdk.v2client import algod

"""Split payement contract where a transaction amount is split between two receivers at provided ratio.
    For that purpose we created a function that accepts contract data as argument"""
def _create_split_contract(
    owner, receiver_1, receiver_2,
    rat_1 = 1, rat_2 = 3,
    expiry_round = 5000000,
    min_pay = 3000, max_fee= 2000
):
    """Create and return split template instance from the provided arguments."""
    return template.Split(owner, receiver_1, receiver_2, rat_1, rat_2,
                          expiry_round, min_pay, max_fee)


def _create_grouped_transactions(split_contract, amount):
    """Create grouped transactions for the provided `split_contract` and `amount`"""
    params = suggested_params()
    return split_contract.get_split_funds_transaction(
        split_contract.get_program(),
        amount,
        1,
        params.first,
        params.last,
        params.gh,
    )

def create_split_transaction(split_contract, amount):
    """Create transaction with provided amount for provided split contract."""
    transactions = _create_grouped_transactions(split_contract, amount)
    transaction_id = process_transactions(transactions)
    return transaction_id


def _algod_client():
    """Instantiate and return Algod client object."""
    algod_address = "http://localhost:4001"
    algod_token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    return algod.AlgodClient(algod_token, algod_address)

## Helper functions

def process_transactions(transaction):
    """Helper function that is reponsible for deploying our smart contract to the Algorand Blockchain"""
    """Send provided grouped `transactions` to network and wait for confirmation"""
    client = _algod_client()
    transaction_id = client.send_transaction(transaction)
    _wait_for_confirmation(client, transaction_id, 4)
    return transaction_id

def _wait_for_confirmation(client, transaction_id, timeout):
    """
    Wait until the transaction is confirmed or rejected, or until `timeout` numbers
    of rounds have passed.
    Args:
            transaction_id (str): The transaction to wait for 
            timeout (int): maximum number of rounds to wait
    Returns:
            dict: pending transaction information, or throws an error if the transaction
            is not confirmed or rejected in the next timeout rounds
    """
    start_round = client.status()['last-round'] + 1
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
        raise Exception (
            "pending tx not found in teimout rounds, timeout value = : {}".format(timeout)
        )


def suggested_params():
    """Returns the suggested params from the algod client"""
    return _algod_client.suggested_params()
