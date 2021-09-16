from algosdk import template

def _create_split_contract(
    owner, receiver_1, receiver_2,
    rat_1 = 1, rat_2 = 3,
    expiry_round = 5000000,
    min_pay = 3000, max_fee= 2000
):
    return template.Split(owner, receiver_1, receiver_2, rat_1, rat_2,
                          expiry_round, min_pay, max_fee)
