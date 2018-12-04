'''AWS encrypt and decrypt utilities'''
import base64
import hashlib
from Crypto import Random
from Crypto.Cipher import AES


class AESCipher(object):

    def __init__(self, key, iv):
        # hash the key to get it in the right size
        self.key = hashlib.sha256(key.encode()).digest()
        self.iv = iv

    def encrypt(self, raw):
        raw = self._pad(raw)
        #iv = Random.new().read(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        return base64.b64encode(self.iv + cipher.encrypt(raw)).hex()

    def decrypt(self, enc):
        enc = bytes.fromhex(enc)
        enc = base64.b64decode(enc)
        iv = enc[:AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return self._unpad(cipher.decrypt(enc[AES.block_size:])).decode('utf-8')

    def _pad(self, s):
        return s + (AES.block_size - len(s) % AES.block_size) * chr(AES.block_size - len(s) % AES.block_size)

    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s)-1:])]

if __name__ == "__main__":
    o = AESCipher('theforceisstrong', bytes.fromhex('0cc60592a486dabf7aeda283d5e3391f'))
    encrpyted_message = o.encrypt('+9720528802120')
    print('encrypted message: %s' % encrpyted_message)
    decrypted_message = o.decrypt(encrpyted_message)
    print('this is the decrypted message')
