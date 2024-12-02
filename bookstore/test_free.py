import hashlib

def deterministic_hash(password):
    # 使用SHA-256哈希函数
    sha_signature = hashlib.sha256(password.encode()).hexdigest()
    return sha_signature

# 示例使用
password = "Tp123123"
encrypted_pw = deterministic_hash(password)
print(f"Encrypted password: {encrypted_pw}")