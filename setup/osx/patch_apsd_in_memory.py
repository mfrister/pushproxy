import os
import sys
from struct import pack
sys.path.append('/Library/Developer/CommandLineTools/Library/PrivateFrameworks/LLDB.framework/Versions/A/Resources/Python')

import lldb


def main():
    if len(sys.argv) != 3:
        sys.stderr.write('Usage: %s <root ca path> <intermediate ca path>\n' %
                         sys.argv[0])
        sys.exit(1)

    root_replacement = sys.argv[1]
    intermediate_replacement = sys.argv[2]

    replacements = replacements_for_certificates(root_replacement,
                                                 intermediate_replacement)

    replacer = ProcessMemoryReplacer('/System/Library/PrivateFrameworks/ApplePushService.framework/apsd')
    replacer.attach_and_stop(False)

    for replacement in replacements:
        replacer.replace(*replacement)
    replacer.detach_and_continue()


def replacements_for_certificates(root_replacement, intermediate_replacement):
    cert_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             '../../certs/entrust')
    root_original = os.path.join(cert_path, 'entrust-root.der')
    intermediate_original = os.path.join(cert_path, 'entrust-intermediate.der')

    return replacements_for_certificate(root_original,
                                        root_replacement) + \
           replacements_for_certificate(intermediate_original,
                                        intermediate_replacement)

def replacements_for_certificate(original_path, replacement_path):
    with open(original_path) as f: original = f.read()
    with open(replacement_path) as f: replacement = f.read()

    if len(original) < len(replacement):
        raise ValueError('Certificate is shorter than replacement (%s)' %
                         replacement_path)

    padding = '\x00' * (len(original) - len(replacement))

    return [
        ('__TEXT', '__text', '\xb9' + pack('<i', len(original)),
                             '\xb9' + pack('<i', len(replacement))),
        ('__TEXT', '__const', original, replacement + padding)
    ]

class ProcessMemoryReplacer(object):
    def __init__(self, process_name):
        self.process_name = process_name

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

    def replace(self, segment, section, needle, replacement):
        """
        Search for needle in section within a segment. Use the needle's offset
        to begin writing the replacement there.

        No checking is done for replacement length vs. needle length, so make
        sure to add padding to shorter values.
        Also no checking is done whether needle appears multiple times in memory.
        In this case the first occurrence is silently used.
        """
        module = self.target.modules[0]
        text_segment = [s for s in module.section_iter() if s.GetName() == segment][0]
        section = [s for s in text_segment if s.GetName() == section][0]
        section_address = section.GetLoadAddress(self.target)

        offset = bytearray(section.data.uint8s).find(needle)

        print "+ Replacing %d bytes at 0x%x" % (len(replacement), section_address + offset)

        error = lldb.SBError()
        self.process.WriteMemory(section_address + offset, replacement, error)
        if not error.Success():
            raise Exception(str(error))

    def detach_and_continue(self):
        self.process.Detach()


if __name__ == '__main__':
    main()
