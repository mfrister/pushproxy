import os
import subprocess
import time
import sys
from struct import pack
sys.path.append('/Library/Developer/CommandLineTools/Library/PrivateFrameworks/LLDB.framework/Versions/A/Resources/Python')

import lldb


def main():
    if len(sys.argv) != 4:
        sys.stderr.write('Usage: %s <root ca path> <intermediate ca path> <leaf path>\n'
                         '\n'
                         'Funny thing: At least on 10.10.1, you just don\'t need this.\n'
                         '             apsd doesn\'t do any certificate pinning. It checks\n'
                         '             things, but doesn\'t fail if the certificate is.\n'
                         '             trusted in the keychain.\n'
                         '\n'
                         'This kills apsd, runs it and patches it. apsd uses exponential backoff '
                         'for server connections, so if the first few attempts fail, you\'ll '
                         'have to wait for a while. Killing and automatically patching it '
                         'solves this problem, although the first attempts might still fail, '
                         'before the patches are applied. During patching, the apsd main thread '
                         'is stopped.' % sys.argv[0])
        sys.exit(1)

    replacement_certs = sys.argv[1:4]

    # Kill apsd to work around exponential backoff
    # lldb has a wait-for-process feature, but when using this,
    # section.GetLoadAddress(target) returns 2^64-1, probably an error.
    # So we just kill it, wait, hope it's started and accept a few failed
    # connections.
    subprocess.check_call(['killall', 'apsd'])

    # give apsd time to be restarted by launchd
    time.sleep(0.2)

    replacements = replacements_for_certificates(replacement_certs)
    replacements += [
        # replace 'mov esi, 0x14' with 'mov esi, 0x04', i.e. disable
        # kSecTrustOptionRequireRevPerCert. Not sure this is necessary, but it
        # doesn't hurt (until this patch fails :))
        ('__TEXT', '__text', 'BE14000000'.decode('hex'), 'BE04000000'.decode('hex'))
    ]

    replacer = ProcessMemoryReplacer('/System/Library/PrivateFrameworks/ApplePushService.framework/apsd')
    replacer.attach_and_stop(False)

    for replacement in replacements:
        replacer.replace(*replacement)
    replacer.detach_and_continue()


def replacements_for_certificates(replacements_certs):
    cert_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             '../../certs')
    originals = [os.path.join(cert_path, 'entrust', 'entrust-root.der'),
                 os.path.join(cert_path, 'entrust', 'entrust-intermediate.der'),
                 os.path.join(cert_path, 'pins', 'leaf-1277256594.der')]

    replacements = []
    for original, replacement in zip(originals, replacements_certs):
        replacements += replacements_for_certificate(original, replacement)

    return replacements

def replacements_for_certificate(original_path, replacement_path):
    with open(original_path) as f: original = f.read()
    with open(replacement_path) as f: replacement = f.read()

    if len(original) < len(replacement):
        raise ValueError('Certificate is shorter than replacement (%s)' %
                         replacement_path)

    padding = '\x00' * (len(original) - len(replacement))

    return [
        # replace 'mov ecx, <cert length>'
        #  - let's hope this won't change :)
        ('__TEXT', '__text', '\xb9' + pack('<i', len(original)),
                             '\xb9' + pack('<i', len(replacement))),
        ('__TEXT', '__const', original, replacement + padding)
    ]

class ProcessMemoryReplacer(object):
    def __init__(self, process_name):
        self.process_name = process_name
        self._section_data_cache = {}

    def attach_and_stop(self, wait_for_process=False):
        error = lldb.SBError()
        listener = lldb.SBListener()

        self.debugger = lldb.SBDebugger.Create()

        # We don't want to handle process events for now
        self.debugger.SetAsync(False)

        self.target = self.debugger.CreateTarget(self.process_name)
        self.process = self.target.AttachToProcessWithName(listener,
                                                           self.process_name,
                                                           wait_for_process,
                                                           error)
        if not error.Success():
            raise Exception(str(error))

        self.thread = self.process.GetSelectedThread()
        self.frame = self.thread.GetSelectedFrame()

    def find_section(self, segment_name, section_name):
        module = self.target.modules[0]
        segment = [s for s in module.section_iter() if s.GetName() == segment_name][0]
        section = [s for s in segment if s.GetName() == section_name][0]
        return section

    def section_data(self, section):
        if not section.file_addr in self._section_data_cache:
            self._section_data_cache[section.file_addr] = bytearray(section.data.uint8s)
        return self._section_data_cache[section.file_addr]

    def replace(self, segment_name, section_name, needle, replacement):
        """
        Search for needle in section within a segment. Use the needle's offset
        to begin writing the replacement there.

        No checking is done for replacement length vs. needle length, so make
        sure to add padding to shorter values.
        Also no checking is done whether needle appears multiple times in memory.
        In this case the first occurrence is silently used.
        """
        print "+ Looking for %d bytes" % len(needle)
        section = self.find_section(segment_name, section_name)
        section_address = section.GetLoadAddress(self.target)

        offset = self.section_data(section).find(needle)

        print "+ Replacing %d bytes at 0x%x" % (len(replacement), section_address + offset)

        error = lldb.SBError()
        self.process.WriteMemory(section_address + offset, replacement, error)
        if not error.Success():
            raise Exception(str(error))

    def detach_and_continue(self):
        self.process.Detach()


if __name__ == '__main__':
    main()
