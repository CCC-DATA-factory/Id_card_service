param(
    [string]$EnvPath = "api_keys.env",
    [string]$EncryptedPath = "api_keys.env.enc",
    [string]$SecretKey
)

# Convert the secret key to a 256-bit AES key
$keyBytes = [System.Text.Encoding]::UTF8.GetBytes($SecretKey)
$sha256 = [System.Security.Cryptography.SHA256]::Create()
$aesKey = $sha256.ComputeHash($keyBytes)

# Generate a random 16-byte IV
$iv = New-Object byte[] 16
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($iv)

# Encrypt the file
$aes = [System.Security.Cryptography.Aes]::Create()
$aes.Mode = "CBC"
$aes.Key = $aesKey
$aes.IV = $iv

$encryptor = $aes.CreateEncryptor()
$plainBytes = [System.IO.File]::ReadAllBytes($EnvPath)
$encryptedBytes = $encryptor.TransformFinalBlock($plainBytes, 0, $plainBytes.Length)

# Save IV + Encrypted content
[System.IO.File]::WriteAllBytes($EncryptedPath, $iv + $encryptedBytes)
Write-Host "✅ Encrypted file saved to: $EncryptedPath"
