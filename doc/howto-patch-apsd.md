# Manual apsd patch for iOS devices

## Once: get apsd entitlements

* on iOS device
<code>
cd /System/Library/PrivateFrameworks/ApplePushService.framework
ldid -e apsd
</code>
* copy the resulting entitlements to a local file, e.g. entitlements.xml

## For every patch


* copy apsd from iOS device:
<code>scp root@iphonelocal:/System/Library/PrivateFrameworks/ApplePushService.framework/apsd .</code>
* edit using hex editor, search for `push.apple.com`. Replace using own domain with length of 14 characters.
    * automated: `perl -pi -e 's/push.apple.com/xxx.xxxxxx.xxx/g' apsd-patched`
* create code signature and entitlements: `codesign -f -s "iPhone Developer" --entitlements entitlements.xml apsd-patched`
    * `iPhone Developer` must be valid certificate in keychain
    * see [saurik's page](http://www.saurik.com/id/8) for more information
* on iOS device: remove `apsd` binary
    * This is necessary to invalidate some kernel signature cache. Overwriting the file does not do this.
    * see [fG!'s blog](http://reverse.put.as/2011/01/28/need-help-with-code-signing-in-ios/), especially jan0's comment
* copy `apsd-patched` to /System/Library/PrivateFrameworks/ApplePushService.framework/apsd
    * `scp apsd-patched root@iphone.local:/System/Library/PrivateFrameworks/ApplePushService.framework/apsd`
* on iOS device: `chmod 755 apsd`
* on iOS device: `killall apsd`
