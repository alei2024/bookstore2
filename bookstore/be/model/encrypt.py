import hashlib

def encrypt(password):
    # 使用SHA-256哈希函数
    sha_signature = hashlib.sha256(password.encode()).hexdigest()
    return sha_signature