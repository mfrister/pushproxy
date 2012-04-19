# http://developer.apple.com/library/mac/#documentation/Security/Reference/keychainservices/Reference/reference.html
# http://developer.apple.com/library/mac/#documentation/Security/Conceptual/Security_Overview/Architecture/Architecture.html#//apple_ref/doc/uid/TP30000976-CH202-TPXREF101

# modify keychain file - flip the following bits (see libsecurity_keychain/SecKey.h)
# kSecKeyExtractable (0 -> 1)
# kSecKeyNeverExtractable (1 -> 0)

import logging
import re
import subprocess
import os
from tempfile import NamedTemporaryFile

logging.basicConfig(level=logging.INFO)

r=subprocess.Popen(['defaults','read','/Library/Preferences/com.apple.applepushserviced','StorageId'], stdout=subprocess.PIPE).communicate()[0]
storageId = re.sub(r'[^0-9a-f]+', '', r).decode("hex")

key = [0xa7, 0x98, 0x51, 0x5A, 0xCD, 0xA6, 0xC5, 0x2E,
       0x8F, 0x51, 0xD8, 0xBA, 0xBC, 0x4B, 0xD1, 0xAA]

password = ''
for i in range(0, len(storageId)):
    v = ord(storageId[i])
    password += chr(v^key[i])

logging.info('Keychain password: ' + password.encode('hex'))

original_keychain='/Library/Keychains/applepushserviced.keychain'
keychain_patched=NamedTemporaryFile(suffix='.keychain', delete=False)

# mark items as extractable and not neverExtractable, see libsecurity_keychain/SecKey.h
extractableSearch=     '000004000000040000000008000000000000000000000008000000000000000000000001000000010000000000000001'.decode('hex')
extractableReplaceWith='000004000000040000000008000000000000000000000008000000000000000000000001000000010000000100000000'.decode('hex')

keychain=open(original_keychain, 'rb').read()
keychain=keychain.replace(extractableSearch, extractableReplaceWith)

keychain_patched.write(keychain)

keychain_file=keychain_patched.name
keychain_patched.close()

logging.info('Temporary keychain file: ' + keychain_file)
pkcs8_fh=NamedTemporaryFile(suffix='.pkcs8', delete=False)
pkcs8_file=pkcs8_fh.name
pkcs8_fh.close()

logging.info(subprocess.Popen(['./extract-private-key', keychain_file, password.encode('hex'), pkcs8_file], stdout=subprocess.PIPE).communicate()[0])
os.unlink(keychain_file)

logging.info('Temporary PKCS8 file: ' + pkcs8_file)
private_key = subprocess.Popen(['openssl', 'pkcs8', '-inform', 'DER', '-passin', 'pass:passphrase', '-in', pkcs8_file], stdout=subprocess.PIPE).communicate()[0]
print private_key

# os.unlink(pkcs8_file)
exit(0)
