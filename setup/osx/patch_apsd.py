#!/usr/bin/env python
import os
import stat
import subprocess
import sys
from struct import pack


def main():
    if len(sys.argv) != 4:
        sys.stderr.write('Usage: %s <apsd binary path> ' % sys.argv[0] +
                         '<root ca path> <codesign identity name>\n\n')
        sys.exit(1)

    apsd_path = sys.argv[1]
    certificate_path = sys.argv[2]
    codesign_identity = sys.argv[3]

    certificate = read_file(certificate_path)
    root_cert_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  '../../certs/entrust/entrust-root.der')
    root_certificate = read_file(root_cert_path)

    if len(root_certificate) < len(certificate):
        raise ValueError('Root certificate is shorter than replacement')

    padding = '\x00' * (len(root_certificate) - len(certificate))

    replacements = {
        '\xb9\x60\x04\x00\x00': '\xb9' + pack('<i', len(certificate)),
        root_certificate: certificate + padding
    }

    output_path = apsd_path + '-patched'

    patch(apsd_path, replacements, output_path)

    if not codesign(output_path, codesign_identity):
        raise Exception('Error: codesign failed.')

    make_executable(output_path)
    print 'Success! Patched file written to %s' % output_path


def codesign(path, identity):
    return not subprocess.call(['codesign', '-f', '-s', identity, path],
                               stdout=sys.stdout,
                               stderr=sys.stderr)


def make_executable(path):
    mode = os.stat(path).st_mode | stat.S_IXOTH | stat.S_IXGRP | stat.S_IXUSR
    os.chmod(path, mode)


def patch(path, replacements, output_path):
    binary = read_file(path)

    for needle, replacement in replacements.iteritems():
        if binary.count(needle) != 1:
            raise ValueError(
                "Source binary doesn't contain replacement key " +
                " or it occurs multiple times: %s" % repr(needle))

        binary = binary.replace(needle, replacement)

    with open(output_path, 'wb') as output:
        output.write(binary)


def read_file(path):
    with open(path, 'rb') as f:
        return f.read()


if __name__ == '__main__':
    main()
