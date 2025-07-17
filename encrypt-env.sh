#!/bin/bash

# Usage: ./encrypt-env.sh api_keys.env api_keys.env.enc "SecretKey"

ENV_PATH=${1:-"api_keys.env"}
ENCRYPTED_PATH=${2:-"api_keys.env.enc"}
SECRET_KEY=$3

if [ -z "$SECRET_KEY" ]; then
  echo "Error: SecretKey must be provided as the 3rd argument"
  exit 1
fi

# Generate a 256-bit key (32 bytes) from the SECRET_KEY using SHA256
KEY=$(echo -n "$SECRET_KEY" | openssl dgst -sha256 -binary)

# Generate random 16-byte IV
IV=$(openssl rand -hex 16)

# Encrypt the file with AES-256-CBC, prepend IV to output
# Convert hex IV to binary
IV_BIN=$(echo "$IV" | xxd -r -p)

# Encrypt with OpenSSL: echo IV + encrypted content > output file
{
  echo -n "$IV_BIN"
  openssl enc -aes-256-cbc -K "$(echo -n "$KEY" | xxd -p)" -iv "$IV" -in "$ENV_PATH" -nosalt -nopad
} > "$ENCRYPTED_PATH"

echo "✅ Encrypted file saved to: $ENCRYPTED_PATH"
