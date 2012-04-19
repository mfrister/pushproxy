#!/bin/bash
if [[ "$#" != "2" ]]; then
    echo "Usage: `basename $0` <iOS device host> <push host 14 chars long>"
    exit 64 # EX_USAGE
fi

set -e
IOS_HOST="$1"
PUSH_HOST="$2"

FRAMEWORK_PATH="/System/Library/PrivateFrameworks/ApplePushService.framework"
if ssh "$IOS_HOST" "[ -x \"$FRAMEWORK_PATH/apsd.orig\" ]"; then
	echo "Error: apsd on $IOS_HOST has already been patched."
	echo "$FRAMEWORK_PATH/apsd.orig exists on device, aborting."
	exit 1
fi

ssh "$IOS_HOST" "cp -av \"$FRAMEWORK_PATH/apsd\" \"$FRAMEWORK_PATH/apsd.orig\""

TMPDIR=`mktemp -d /tmp/patch-apsd.XXXXXX`
cd "$TMPDIR"

ssh "$IOS_HOST" ldid -e "$FRAMEWORK_PATH/apsd" > entitlements.xml
scp "$IOS_HOST:$FRAMEWORK_PATH/apsd" ./apsd

APSD='./apsd'

cp -av "$APSD" "$APSD-$PUSH_HOST"
perl -pi -e "s/push.apple.com/$PUSH_HOST/g" "$APSD-$PUSH_HOST"
cp -av "$APSD-$PUSH_HOST" "$APSD-$PUSH_HOST-entitlements-codesigned"
codesign -f -s "iPhone Developer" --entitlements entitlements.xml "$APSD-$PUSH_HOST-entitlements-codesigned"

echo "Deleting original apsd and uploading new apsd to device..."
# Deleting and creating is necessary to invalidate some kernel signature cache. Overwriting the file does not do this.
# see [fG!'s blog](http://reverse.put.as/2011/01/28/need-help-with-code-signing-in-ios/), especially jan0's comment
ssh "$IOS_HOST" rm "\"$FRAMEWORK_PATH/apsd\""
scp "$APSD-$PUSH_HOST-entitlements-codesigned" "$IOS_HOST:$FRAMEWORK_PATH/apsd"

rm -r "$TMPDIR"
echo "Done"