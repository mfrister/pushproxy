from collections import namedtuple
from struct import unpack, unpack_from
from subprocess import Popen, PIPE

from extractkeychain.extractkeychain import kcdecrypt, \
                                            magicCmsIV as magic_cms_iv


# see ssblob.h KeyBlob, 24 bytes encoded
KeyBlobHeader = namedtuple('KeyBlobHeader', 'magic version start_crypto_blob'
                                            ' total_length iv')
# see cssmtype.h CSSM_KEYHEADER, 80 bytes encoded
CssmKeyHeader = namedtuple('CssmKeyHeader', 'header_version csp_id blob_type'
                                            ' format algorithm_id key_class'
                                            ' logical_key_size_in_bits'
                                            ' key_attr key_usage start_date'
                                            ' end_date wrap_algorithm_id'
                                            ' wrap_mode reserved')


 #(4208854801, 256, 1032, '\x00\x00\x06\x98\x9e6\xc6\xe5')
def parse_key_blob(data):
    """Parse a KeyBlob, see ssblob.h"""
    key_blob_header = KeyBlobHeader(*unpack('!IIII8s', data[:24]))
    cssm_values = unpack('!I16sIIIIIII8s8sIIII', data[24:104])
    cssm_values = list(cssm_values)[:14]

    cssm_key_header = CssmKeyHeader(*cssm_values)
    return (key_blob_header, cssm_key_header)


def decrypt_key(data, master_key):
    """
        Decrypt key in a KeyBlob, see wrapKeyCms.cpp (libsecurity_apple_csp)

        Return tuple (description, plain_key)
    """
    key_header, cssm_header = parse_key_blob(data)
    blob_offset = key_header.start_crypto_blob
    temp3 = kcdecrypt(master_key, magic_cms_iv, data[blob_offset:])
    temp2 = temp3[::-1]  # reverse
    temp1 = temp2[8:]
    iv2 = temp2[:8]
    plain = kcdecrypt(master_key, iv2, temp1)
    description_length = unpack_from('!I', plain)[0]
    return (plain[4:4 + description_length], plain[4 + description_length:])


def decrypt_rsa_key(data, master_key):
    """Decrypt an RSA key, return it in DER encoding"""
    description, plain_key = decrypt_key(data, master_key)
    cmd = 'openssl asn1parse -inform DER |grep "HEX DUMP"'
    pipe = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdout, stderr = pipe.communicate(plain_key)
    if pipe.returncode != 0:
        raise Exception("decrypt_rsa_key: command failed: " + cmd)

    return stdout.rsplit(':', 1)[1].strip().decode('hex')


def rsa_key_der_to_pem(der_key):
    cmd = 'openssl rsa -inform DER'.split(' ')
    process = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    pem_key, stderr = process.communicate(der_key)
    if process.returncode != 0:
        raise Exception('rsa_key_der_to_pem: command failed: "' + cmd
                         + '" stderr: ' + stderr)
    return pem_key
