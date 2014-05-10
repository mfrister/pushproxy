# Find X.509 certificates in DER-encoding with
# length >= 256 and <= 65535 bytes and beginning with two nested sequences.
#
# Requires pyOpenSSL (tested with 0.13,
#                     might be installed by default on OS X)


from __future__ import print_function
import argparse
import re
import struct
import sys

from OpenSSL import crypto

def main():
    args = parse_args()

    with open(args.file, 'rb') as f:
        contents = f.read()

    find_certs(contents, dump_certs=args.dump)

def parse_args():
    parser = argparse.ArgumentParser(description=
        'Find X.509 certificates in DER-encoding with \n' \
        'length >= 256 and <= 65535 bytes and beginning with ' \
        'two nested sequences.')
    parser.add_argument('file', metavar='FILE', type=str,
                       help='file to look for certificates in')
    parser.add_argument('-d', '--dump',
        action='store_true',
        help='Dump the found certificates in PEM-encoding to stdout')

    return parser.parse_args()


def find_cert_candidate_positions(data):
    # Certificate usually begin with an ASN.1 sequence. A sequence begins with
    # 0x30 followed by a length. Ignoring lengths < 128 bytes.
    #
    # Long form: Two to 127 octets. Bit 8 of first octet has value "1" and
    # bits 7-1 give the number of additional length octets. Second and
    # following octets give the length, base 256, most significant digit first.
    # See http://luca.ntop.org/Teaching/Appunti/asn1.html
    return [m.start() for m in re.finditer("\x30\x82..\x30", data)]

def sequence_length(data, position):
    return struct.unpack_from('!H', data, position+2)[0]

def parse_cert(data, position, length):
    # add 1 for sequence type
    # add 3 for length 0x82 0xXX 0xXX
    cert_data = data[position:position+1+3+length]

    return crypto.load_certificate(crypto.FILETYPE_ASN1, cert_data)

def dump_cert(cert):
    print(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

def find_certs(data, dump_certs=False):
    last_end = 0
    certs = []

    for position in find_cert_candidate_positions(data):
        if position < last_end:
            # nested sequence from previous certificate
            continue
        length = sequence_length(data, position)

        try:
            cert = parse_cert(data, position, length)
        except Exception, e:
            print('- %d Failed to parse cert (length %d): %s' %
                  (position, length, e), file=sys.stderr)
            continue

        print('+ %d Found cert with CN "%s" and serial "%s"' %
              (position, cert.get_subject().commonName, cert.get_serial_number()),
              file=sys.stderr)

        if dump_certs:
            dump_cert(cert)

        certs.append(cert)

        last_end = position + length

    return certs


if __name__ == "__main__":
    main()