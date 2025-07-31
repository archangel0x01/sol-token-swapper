# Jupiter Token Buyer

A Python script to automatically buy Solana tokens using SOL through the Jupiter DEX aggregator. This tool provides a simple command-line interface for swapping SOL to any SPL token with customizable slippage tolerance.

## Features

- 🚀 **Jupiter Integration**: Uses Jupiter's v6 API for optimal routing and pricing
- 💰 **SOL to Token Swaps**: Buy any SPL token using SOL
- 🎯 **Customizable Slippage**: Set your preferred slippage tolerance
- 🔐 **Secure Wallet Management**: Uses local wallet file for signing transactions
- 📊 **Real-time Quotes**: Get live pricing and price impact information
- ✅ **Transaction Confirmation**: Automatically waits for and confirms transactions

## Prerequisites

- Python 3.7+
- A Solana wallet with sufficient SOL balance
- Internet connection

## Installation

1. Clone this repository:
```bash
git clone https://github.com/archangel0x01/sol-token-swapper.git
cd sol-token-swapper
```

2. Install required packages:
```bash
pip install httpx solders solana base58
```

3. Create a `wallet.json` file in the project directory:
```json
{
  "secretKey": "YOUR_BASE58_SECRET_KEY_HERE"
}
```

## Usage

Run the script:
```bash
python swapper.py
```

You'll be prompted to enter:
- **Token mint address**: The address of the token you want to buy
- **SOL amount**: How much SOL to spend (e.g., 0.001)
- **Slippage tolerance**: Acceptable slippage percentage (default: 1%)
