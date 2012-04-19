# execute this by hand

# exit on errors
set -e

if [ $#  -ne "1" ]; then
	echo "Usage: `basename $0` <iOS device hostname>"
	echo "  hostname could be e.g. iphone.local"
	exit 64 # EX_USAGE
fi

TMPDIR=certs/device/tmp
mkdir -p "$TMPDIR"

IOS_HOST="$1"
scp tools/PushFix/nimble "$IOS_HOST":/private/var/Keychains
ssh "$IOS_HOST" 'cd /private/var/Keychains && chmod +x nimble && ./nimble'

# cd to somewhere in iphone-certs here
scp "$IOS_HOST":/private/var/Keychains/*.bin "$TMPDIR"

cd "$TMPDIR"

set -e
COMMON_NAME=$(openssl x509 -noout -subject -inform DER -in push-cert.bin | cut -f2 -d/ | cut -f2 -d=)
openssl x509 -in push-cert.bin -inform DER -out push-cert.pem
openssl rsa -in push-key.bin -inform DER -out push-key.pem

OUTPUT_FILE="../$COMMON_NAME.pem"
cat push-key.pem push-cert.pem > "$OUTPUT_FILE"

echo "Created $(pwd)/$OUTPUT_FILE"
cd - > /dev/null
