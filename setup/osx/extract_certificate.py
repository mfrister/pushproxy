#!/usr/bin/env python
import platform
import sys
from collections import namedtuple
from os.path import dirname, join, realpath
from subprocess import Popen, PIPE

from bplist.bplist import BPlistReader
from extractkeychain.extractkeychain import getdbkey

from keychain import Keychain
from keys import decrypt_rsa_key, rsa_key_der_to_pem


OSX_SETUP_PATH = realpath(dirname(realpath(__file__)))
sys.path.append(OSX_SETUP_PATH)
CERT_PATH = realpath(join(dirname(realpath(__file__)), '../../certs/device'))


def normalize_version(version):
    return [int(x) for x in version.split(".")]


ApsdConfiguration = namedtuple('ApsdConfiguration', 'preferences keychain')


def get_apsd_configuration():
    version = platform.mac_ver()[0]
    if normalize_version(version) < [10, 8]:
        apsd_name = 'applepushserviced'
    else:
        apsd_name = 'apsd'
    return ApsdConfiguration(
        preferences='/Library/Preferences/com.apple.%s.plist' % apsd_name,
        keychain='/Library/Keychains/%s.keychain' % apsd_name,
    )


def get_apsd_preferences(prefs_file=None):
    if not prefs_file:
        prefs_file = get_apsd_configuration().preferences
    prefs = BPlistReader.plistWithString(open(prefs_file).read())
    return prefs


def calculate_apsd_keychain_password(apsd_prefs):
    storage_id = apsd_prefs['StorageId']

    key = [0xa7, 0x98, 0x51, 0x5A, 0xCD, 0xA6, 0xC5, 0x2E,
           0x8F, 0x51, 0xD8, 0xBA, 0xBC, 0x4B, 0xD1, 0xAA]

    password = ''
    for i in range(0, len(storage_id)):
        v = ord(storage_id[i])
        password += chr(v ^ key[i])

    return password


def extract_certificate(keychain_file):
    """
        Extract certificate from keychain using security utility

        Return certificate in PEM encoding. Behaviour is unknown if the
        keychain contains multiple certificates.
    """
    cmd = ['security', 'export', '-k', keychain_file, '-t', 'certs', '-p']
    process = Popen(cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise Exception("extract_certificate: command failed: '%s' stdout: %s" %
                        (cmd, stdout))
    return stdout


def main():
    keychain_file = get_apsd_configuration().keychain
    fh = open(keychain_file)
    apsd_prefs = get_apsd_preferences()
    password = calculate_apsd_keychain_password(apsd_prefs)
    master_key = getdbkey(fh, password)
    keychain = Keychain(fh)
    # record type 16 - private keys
    # see CSSM_DL_DB_RECORD_PRIVATE_KEY in cssmtype.h (libsecurity_cssm)
    table = keychain.table_by_record_type(16)
    record = table.find_record_by_attribute('PrintName',
                                            apsd_prefs['CertificateName'])

    key = decrypt_rsa_key(record.data, master_key)
    key_pem = rsa_key_der_to_pem(key)
    certificate_pem = extract_certificate(keychain_file)

    push_cert_file = join(CERT_PATH, apsd_prefs['CertificateName'] + '.pem')

    cert_fh = sys.stderr
    if len(sys.argv) > 1 and sys.argv[1] == '-f':
        cert_fh = open(push_cert_file, 'wb')
        sys.stderr.write('Writing private key and certificate to %s\n' %
                         push_cert_file)

    cert_fh.write(key_pem)
    cert_fh.write(certificate_pem)


if __name__ == '__main__':
    main()
