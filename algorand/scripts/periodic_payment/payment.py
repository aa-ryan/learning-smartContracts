from pyteal import Int, Bytes, Addr, Txn, And, Or, Global, compileTeal, Mode

# template variable

tmpl_fee = Int(1000)
tmpl_period = Int(1000)
tmpl_dur = Int(1000)
tmpl_x = Bytes("base64", "y9OJ5MRLCHQj8GqbikAUKMBI7hom+SOj8dlopNdNHXI=")
tmpl_amt = Int(2000)
tmpl_rcv = Addr("ZZAF5ARA4MEC5PVDOP64JM5O5MQST63Q2KOY2FLYFLXXD3PFSNJJBYAFZM")
tmpl_timeout = Int(30000)


# Checks the type of transaction, in this case checking for pay transactio
# Check the fee to make sure that it is less than some reasonable amount. 

periodic_pay_core = And(Txn.type_enum() == Int(1),
                            Txn.fee() < tmpl_fee)

# Checks that the transaction will not be closing out the balance of the address
# setting receiver to be intended receiver and amount of transaction to intended amount
periodic_pay_transfer = And(Txn.close_remainder_to() == Global.zero_address(),
                                Txn.receiver() == tmpl_rcv,
                                Txn.amount() == tmpl_amt,
                                Txn.first_valid() % tmpl_period == Int(0),  # allows the transfer the happen every tmpl_period rounds for tmpl_dur
                                Txn.last_valid() == tmpl_dur + Txn.first_valid(),
                                Txn.lease() == tmpl_x)

# Txn.first_valid() > tmpl_timeout then remaining balance is closed to tmpl_rcv
periodic_pay_close = And(Txn.close_remainder_to() == tmpl_rcv,
                         Txn.receiver() == Global.zero_address(),
                         Txn.first_valid() > tmpl_timeout,
                         Txn.amount() == Int(0))

# combining all conditions
periodic_pay_escrow = And(periodic_pay_core, Or(periodic_pay_transfer, periodic_pay_close))

print(compileTeal(periodic_pay_escrow, mode=Mode.Signature, version=2))
