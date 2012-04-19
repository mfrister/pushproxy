#!/bin/sh
gcc extract-private-key.c -o extract-private-key -framework Security -framework CoreFoundation $@
