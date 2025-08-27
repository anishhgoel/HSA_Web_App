# HSA Web Application - Local Demo

A simple Health Savings Account (HSA) web application that demonstrates the core lifecycle: account creation, funding, card issuance, and transaction.

## Features

- **Create Account**: Simple user registration and HSA account creation
- **Deposit Funds**: Add virtual funds to your HSA
- **Issue Card**: Generate virtual debit cards linked to your HSA balance
- **Validate Transactions**: Simulate purchases with automatic validation of IRS-qualified medical expenses



### Setup Instructions

1. **Clone/Download** this repository to your local machine

2. **Create and activate a virtual environment**: (python or python3 in commands depending on version of python installed)
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   
   ```

3. **Install dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python3 app.py
   ```

5. **Open your browser** and navigate to:
   ```
   http://127.0.0.1:5000
   ```

6. **Youtube Link** :
https://www.youtube.com/watch?v=zPdaGFZ2TGw&ab_channel=Anish