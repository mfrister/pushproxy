#!/usr/bin/env python
import os
import sys
from plistlib import writePlistToString, Data

from OpenSSL import crypto


def der_cert_from_pem_file(cert_file):
    cert_pem = open(cert_file).read()
    cert = crypto.dump_certificate(crypto.FILETYPE_ASN1,
                crypto.load_certificate(crypto.FILETYPE_PEM, cert_pem))
    return cert


def sign_bag(data, cert_file):
    private_key_pem = open(cert_file).read()
    private_key = crypto.load_privatekey(crypto.FILETYPE_PEM, private_key_pem)
    return crypto.sign(private_key, data, 'sha1')


def generate_bag(content, cert_file):
    content_plist = writePlistToString(content)
    bag = {
        'bag': Data(content_plist),
        'certs': [Data(der_cert_from_pem_file(cert_file))],
        'signature': Data(sign_bag(content_plist, cert_file)),
    }
    return writePlistToString(bag)


def generate_apsd_bag(host, cert_file):
    bag_content = {
        'APNSCourierHostcount': 50,
        'APNSCourierHostname': host,
        'APNSCourierStatus': True,
        'ClientConnectionRetryAttempts': 100}
    return generate_bag(bag_content, cert_file)


def serve_apsd_bag(hostname, cert_file):
    from flask import Flask
    app = Flask(__name__)
    app.debug = True

    @app.route("/bag")
    def bag():
        return generate_apsd_bag(hostname, cert_file)
    app.run(host='0.0.0.0', port=80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write('Usage: %s <push hostname> <certificate> [-s]\n'
                         '  <certificate> must be a file containing a'
                         ' private-key and \n'
                         '                certificate in in PEM-encoding\n'
                         '  -s Serve bag instead of writing it to stdout\n'
                         '     Requires flask\n'
                         % sys.argv[0])
        exit(os.EX_USAGE)
    hostname = sys.argv[1]
    cert_file = sys.argv[2]
    if len(sys.argv) > 3 and sys.argv[3] == '-s':
        serve_apsd_bag(hostname, cert_file)
    else:
        sys.stdout.write(generate_apsd_bag(hostname, cert_file))
