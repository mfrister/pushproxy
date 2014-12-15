#!/usr/bin/env python
import os
import stat
import subprocess
import sys
from struct import pack


def main():
    if len(sys.argv) != 5:
        sys.stderr.write('Usage: %s <apsd binary path> ' % sys.argv[0] +
                         '<root ca path> <intermediate ca path> <codesign identity name>\n\n')
        sys.exit(1)

    apsd_path = sys.argv[1]
    root_replacement = sys.argv[2]
    intermediate_replacement = sys.argv[3]
    codesign_identity = sys.argv[4]

    replacements = []

    cert_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             '../../certs/entrust')
    root_original = os.path.join(cert_path, 'entrust-root.der')
    replacements += replacements_for_certificates(root_original,
                                                  root_replacement)

    intermediate_original = os.path.join(cert_path, 'entrust-intermediate.der')
    replacements += replacements_for_certificates(intermediate_original,
                                                  intermediate_replacement)

    output_path = apsd_path + '-patched'

    patch(apsd_path, dict(replacements), output_path)

    if not codesign(output_path, codesign_identity):
        raise Exception('Error: codesign failed.')

    make_executable(output_path)
    print 'Success! Patched file written to %s' % output_path


def replacements_for_certificates(original_path, replacement_path):
    original = read_file(original_path)
    replacement = read_file(replacement_path)

    if len(original) < len(replacement):
        raise ValueError('Root certificate is shorter than replacement')

    padding = '\x00' * (len(original) - len(replacement))

    return [
        ('\xb9' + pack('<i', len(original)), '\xb9' + pack('<i', len(replacement))),
        (original, replacement + padding)
    ]

def codesign(path, identity):
    return not subprocess.call(['codesign',
                                '--force',
                                # '--preserve-metadata=entitlements',
                                '--sign', identity,
                                path],
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
