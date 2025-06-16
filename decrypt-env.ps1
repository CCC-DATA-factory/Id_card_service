param(
    [string]$EncryptedPath = "api_keys.env.enc",
    [string]$OutputPath = "api_keys.env",
    [string]$SecretKey
)

# Read encrypted file and split IV and content
$allBytes = [System.IO.File]::ReadAllBytes($EncryptedPath)
$iv = $allBytes[0..15]
$encryptedBytes = $allBytes[16..($allBytes.Length - 1)]

# Derive AES key from secret
$keyBytes = [System.Text.Encoding]::UTF8.GetBytes($SecretKey)
$sha256 = [System.Security.Cryptography.SHA256]::Create()
$aesKey = $sha256.ComputeHash($keyBytes)

# Decrypt
$aes = [System.Security.Cryptography.Aes]::Create()
$aes.Mode = "CBC"
$aes.Key = $aesKey
$aes.IV = $iv

$decryptor = $aes.CreateDecryptor()
$plainBytes = $decryptor.TransformFinalBlock($encryptedBytes, 0, $encryptedBytes.Length)

[System.IO.File]::WriteAllBytes($OutputPath, $plainBytes)
Write-Host "🔓 Decrypted file saved to: $OutputPath"
