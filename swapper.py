import json
import httpx
import base64
import base58
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.message import to_bytes_versioned
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Confirmed

# --- Configuration ---
# Make sure you have a wallet.json file in the same directory with your secret key
# { "secretKey": "YOUR_BASE58_SECRET_KEY" }
WALLET_FILE = "wallet.json"
RPC_URL = "https://api.mainnet-beta.solana.com"  # Using a public RPC, but a private one is recommended

# Jupiter API endpoints
QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
SWAP_URL = "https://quote-api.jup.ag/v6/swap"

# SOL Mint address
SOL_MINT = "So11111111111111111111111111111111111111112"

def get_wallet() -> Keypair:
    """Loads the wallet keypair from the wallet.json file."""
    try:
        with open(WALLET_FILE, 'r') as f:
            wallet_data = json.load(f)
            secret_key_b58 = wallet_data["secretKey"]
            # Handle both base58 string and byte array formats
            if isinstance(secret_key_b58, str):
                return Keypair.from_base58_string(secret_key_b58)
            else:
                # If it's a byte array (list of numbers)
                return Keypair.from_bytes(bytes(secret_key_b58))
    except FileNotFoundError:
        print(f"Error: {WALLET_FILE} not found.")
        exit(1)
    except json.JSONDecodeError:
        print(f"Error: Could not decode {WALLET_FILE}. Make sure it's a valid JSON.")
        exit(1)
    except KeyError:
        print(f"Error: 'secretKey' not found in {WALLET_FILE}.")
        exit(1)
    except Exception as e:
        print(f"Error loading wallet: {e}")
        exit(1)


async def get_quote(session, input_mint: str, output_mint: str, amount: int, slippage_bps: int = 50):
    """
    Gets a swap quote from the Jupiter API.
    """
    print(f"Getting quote for {amount / 1e9} SOL to {output_mint}...")
    params = {
        'inputMint': input_mint,
        'outputMint': output_mint,
        'amount': amount,
        'slippageBps': slippage_bps
    }
    try:
        response = await session.get(QUOTE_URL, params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        print(f"Error getting quote from Jupiter API: {e}")
        print(f"Response body: {e.response.text}")
        return None
    except Exception as e:
        print(f"Unexpected error getting quote: {e}")
        return None


async def get_swap_transaction(session, quote_response, user_public_key: str):
    """
    Gets the swap transaction from the Jupiter API.
    """
    print("Building swap transaction...")
    payload = {
        "quoteResponse": quote_response,
        "userPublicKey": user_public_key,
        "wrapAndUnwrapSol": True,
        "dynamicComputeUnitLimit": True,
        "prioritizationFeeLamports": "auto"
    }
    try:
        response = await session.post(SWAP_URL, json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        print(f"Error getting swap transaction from Jupiter API: {e}")
        print(f"Response body: {e.response.text}")
        return None
    except Exception as e:
        print(f"Unexpected error getting swap transaction: {e}")
        return None


async def buy_token_with_sol(token_mint: str, sol_amount: float, slippage_bps: int = 100):
    """
    Buy tokens using SOL through Jupiter DEX aggregator.
    
    Args:
        token_mint: The mint address of the token to buy
        sol_amount: Amount of SOL to spend
        slippage_bps: Slippage tolerance in basis points (100 = 1%)
    """
    # 1. Load wallet
    wallet = get_wallet()
    user_public_key = str(wallet.pubkey())
    print(f"Wallet loaded. Public key: {user_public_key}")

    if sol_amount <= 0:
        print("Error: SOL amount must be positive.")
        return False

    amount_in_lamports = int(sol_amount * 1e9)
    print(f"Buying {sol_amount} SOL worth of {token_mint}")

    # 2. Perform swap
    async with httpx.AsyncClient(timeout=30.0) as session:
        # Get quote
        quote_response = await get_quote(session, SOL_MINT, token_mint, amount_in_lamports, slippage_bps)
        if not quote_response:
            print("Failed to get quote")
            return False

        print("Quote received:")
        print(f"  - Input: {int(quote_response['inAmount']) / 1e9} SOL")
        print(f"  - Output: {quote_response['outAmount']} tokens")
        print(f"  - Price Impact: {quote_response.get('priceImpactPct', 'N/A')}%")

        # Get swap transaction
        swap_data = await get_swap_transaction(session, quote_response, user_public_key)
        if not swap_data:
            print("Failed to get swap transaction")
            return False

        # 3. Sign and send transaction
        try:
            swap_transaction_b64 = swap_data['swapTransaction']
            raw_tx_bytes = base64.b64decode(swap_transaction_b64)
            raw_tx = VersionedTransaction.from_bytes(raw_tx_bytes)
            
            # Sign the transaction using the proper method for VersionedTransaction
            signature = wallet.sign_message(to_bytes_versioned(raw_tx.message))
            signed_tx = VersionedTransaction.populate(raw_tx.message, [signature])

            # Send the transaction
            solana_client = Client(RPC_URL)
            print("Sending transaction...")
            
            opts = TxOpts(
                skip_preflight=False,
                preflight_commitment=Confirmed,
                max_retries=3
            )
            
            # Convert signed transaction to bytes for sending
            result = solana_client.send_raw_transaction(bytes(signed_tx), opts=opts)
            
            if result.value:
                tx_signature = result.value
                print(f"Transaction sent successfully!")
                print(f"Signature: {tx_signature}")
                print(f"View on Solscan: https://solscan.io/tx/{tx_signature}")
                
                # Wait for confirmation
                print("Waiting for confirmation...")
                confirmation = solana_client.confirm_transaction(tx_signature, commitment=Confirmed)
                if confirmation.value[0].confirmation_status:
                    print("Transaction confirmed!")
                    return True
                else:
                    print("Transaction failed to confirm")
                    return False
            else:
                print("Failed to send transaction - no signature returned")
                return False
                
        except Exception as e:
            print(f"Error processing transaction: {e}")
            return False


async def main():
    """
    Main function to execute the swap.
    """
    # Get user input
    output_mint = input("Enter the mint address of the token you want to buy: ").strip()
    sol_amount_str = input("Enter the amount of SOL to swap: ").strip()
    slippage_str = input("Enter slippage tolerance in % (default 1%): ").strip()

    try:
        sol_amount = float(sol_amount_str)
        if sol_amount <= 0:
            raise ValueError("Amount must be positive.")
    except ValueError as e:
        print(f"Invalid amount: {e}")
        return

    try:
        if slippage_str:
            slippage_percent = float(slippage_str)
            slippage_bps = int(slippage_percent * 100)  # Convert % to basis points
        else:
            slippage_bps = 100  # Default 1%
    except ValueError:
        print("Invalid slippage, using default 1%")
        slippage_bps = 100

    # Execute the buy
    success = await buy_token_with_sol(output_mint, sol_amount, slippage_bps)
    if success:
        print("Token purchase completed successfully!")
    else:
        print("Token purchase failed!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
