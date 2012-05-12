#!/usr/bin/env bash

BINARY_PATH="/System/Library/PrivateFrameworks/ApplePushService.framework/applepushserviced"
BINARY="$(basename $BINARY_PATH)"
BACKUP_SUFFIX=".orig"
CERT_NAME="iPhone Developer"

if [[ "$#" != "1" ]]; then
    echo "Usage: `basename $0` <push host 14 chars long>"
    echo
    echo "Warning: This script modifies $BINARY_PATH"
    echo "         It saves a backup in the same directory as $BINARY.orig"
    exit 64 # EX_USAGE
fi

set -e
PUSH_HOST="$1"

BACKUKP_PATH="$BINARY_PATH$BACKUP_SUFFIX"

FRAMEWORK_PATH="/System/Library/PrivateFrameworks/ApplePushService.framework"
if [ -e "$BACKUKP_PATH" ]; then
    echo "Error: $BACKUKP_PATH exists, $BINARY has probably already been patched."
    echo "Delete it if you are sure its the original, e.g. after an OS X update."
    exit 1
fi

sudo cp -av "$BINARY_PATH" "$BACKUKP_PATH"

TMPDIR=`mktemp -d /tmp/patch-$BINARY.XXXXXX`
cd "$TMPDIR"

cp -av "$BINARY_PATH" ./$BINARY

perl -pi -e "s/push.apple.com/$PUSH_HOST/g" "$BINARY"

codesign -f -s "$CERT_NAME" "$BINARY"

# delete and create seems to be necessary also on OS X to clear a kernel
# signature cache
sudo rm "$BINARY_PATH"
sudo cp -av "$BINARY" "$BINARY_PATH"

rm -r "$TMPDIR"
echo "Done"

echo "After restarting applepushserviced, you need to extract the"
echo "push certificate again. The binary has a new signature, so Keychain"
echo "doesn't allow it to access the old certificate, therefore "
echo "applepushserviced requests a new one."
