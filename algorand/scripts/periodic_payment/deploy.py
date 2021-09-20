from pyteal import Mode, execute
import uuid, params, base64
from algosdk import algod, transaction, account, mnemonic
from pyteal.compiler.compiler import compileTeal
from payment import periodic_pay_escrow

# -- compile and send transaction using goal and python sdk --

teal_source = compileTeal(periodic_pay_escrow, mode=Mode.Signature, version=2)

# compile teal
teal_file = str(uuid.uuid4()) + '.teal'
with open(teal_file, 'w+') as f:
    f.write(teal_source)

lsig_fname = str(uuid.uuid4()) + '.tealc'

stdout, stderr = execute(["goal", "clerk", "compile", "-o", lsig_fname, teal_file])

if stderr != "":
    print(stderr)
    raise
elif len(stdout) < 59:
    print("Error in compile teal")
    raise

with open (lsig_fname, 'rb') as f:
    teal_bytes = f.read()
lsig = transaction.LogicSig(teal_bytes)

# Create algod client

acl = algod.AlgodClient(params.algod_token, params.algod_address)

# Recover the account that is wanting to delegate signature
passphrase = "This is a test and this test seems to be success i think so i don't know about you this is just a passpharse string bye"
sk = mnemonic.to_private_key(passphrase)

addr = account.address_from_private_key(sk)
print("Address of Sender/Delgator: "  + addr)

# sign the logic signature with account sk
lsig.sign(sk)

# get suggested parameters
params = acl.suggested_params()
gen = params["genesisID"]
gh = params["genesishashb64"]
startRound = params["lastRound"] - (params["lastRound"] % 1000)
endRound = startRound + 1000
fee = 1000
amount = 2000
receiver = "ZZAF5ARA4MEC5PVDOP64JM5O5MQST63Q2KOY2FLYFLXXD3PFSNJJBYAFZM"
lease = base64.b64decode("y9OJ5MRLCHQj8GqbikAUKMBI7hom+SOj8dlopNdNHXI=")

print(params["lastRound"])
print(startRound)
print(endRound)

# create a transaction
txn = transaction.PaymentTxn(addr, fee, startRound, endRound, gh, receiver, amount, flat_fee=True, lease=lease)

# Create the LogicSigTransaction with contract account LogicSig
lstx = transaction.LogicSigTransaction(txn, lsig)

# write to file
txns = [lstx]
transaction.write_to_file(txns, "p_pay.stxn")

# send raw LogicSigTransaction to network
txid = acl.send_transaction(lstx)
print("Transaction ID: " + txid)

