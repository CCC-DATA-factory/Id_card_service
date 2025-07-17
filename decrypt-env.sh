#!/bin/bash
# chmod +x decrypt-env.sh
# ./decrypt-env.sh -e api_keys.env.enc -o api_keys.env -k "your-secret-key"



EncryptedPath="api_keys.env.enc"
OutputPath="api_keys.env"
SecretKey=""

# Parse params
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -e|--encrypted) EncryptedPath="$2"; shift ;;
        -o|--output) OutputPath="$2"; shift ;;
        -k|--key) SecretKey="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [[ -z "$SecretKey" ]]; then
    echo "SecretKey is required. Use -k or --key to provide it."
    exit 1
fi

# Derive AES key from SecretKey using SHA256
AES_KEY=$(echo -n "$SecretKey" | sha256sum | cut -d' ' -f1)

# Extract IV (first 16 bytes) to iv.bin
dd if="$EncryptedPath" bs=1 count=16 of=iv.bin 2>/dev/null

# Extract encrypted content after first 16 bytes
dd if="$EncryptedPath" bs=1 skip=16 of=data.enc 2>/dev/null

# Decrypt using openssl
openssl enc -aes-256-cbc -d -in data.enc -out "$OutputPath" -K "$AES_KEY" -iv "$(xxd -p iv.bin)" -nopad 2>/dev/null

# Clean temp files
rm iv.bin data.enc

echo "🔓 Decrypted file saved to: $OutputPath"
