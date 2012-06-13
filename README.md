# PushProxy

PushProxy is a **man-in-the-middle proxy** for **iOS and OS X Push Notifications**. It decodes the push protocol and outputs messages in a readable form. It also provides APIs for handling messages and sending push notifications directly to devices without sending them via Apple's infrastructure.

For a reference on the push protocol, see `doc/apple-push-protocol-ios5-lion.md`. iOS4 and earlier used another version of the protocol, described in `doc/apple-push-protocol-ios4.md`. This proxy only supports the iOS5 protocol.

I tested only using jailbroken iOS devices, but it may be possible to use a push certificate from a jailbroken device and use it to connect a non-jailbroken device to Apple's servers. At least some apps using push notifications will be confused if you do this, but I think this was a way for hacktivated iPhones to get a push certificate.

## Setup

The proxy is written in Python, I recommend setting up a virtualenv and installing the requirements:

    pip install -r src/requirements.txt

Setting up PushProxy requires redirecting push connections to your server and setting up X.509 certificates for SSL authentication.

The push protocol uses SSL for client and server authentication. You need to extract the device certificate and give it to the proxy so it can authenticate itself as device against Apple. You also need to make the device trust your proxy since you are impersonating Apple's servers.

### Server certificate

Note: This certificate creation only works for WiFi connections, see below if you want the proxy to work via 3G.

You need to create a SSL server certificate and install it on your device. It's common name should be:

    courier.push.apple.com

Then place the certificate in PEM encoding at the following path:

    certs/courier.push.apple.com/server.pem

You can install the certificate on iOS devices via Safari or iPhone Configuration Utility.

On OS X you can use keychain access to install the certificate, make sure to install it in the System keychain, not your login keychain. Mark it as trusted, Keychain Access should then display it as 'marked as trusted for all users'.

### Extract iOS Certificates

First, download the [nimble](http://xs1.iphwn.org/releases/PushFix.zip) tool, extract `PushFix.zip` and place `nimble` into `setup/ios`. The following script will copy the tool to your iOS device, run it and copy the extracted certificates back to your computer. It assumes you have **SSH** running on your device. I recommend setting up key-based authentication, otherwise you will be typing your password a few times.

Make sure you are in the pushproxy root directory, otherwise the script will fail.

    cd pushproxy
    setup/ios/extract-and-convert-certs.sh root@<device hostname>

You can find the extracted certificates in `certs/device`. Both public and private key are in one PEM-file.

### Extract OS X Certificates

Note: If you want to connect at least one device via a patched push daemon, you need to patch the push daemon on OS X first.

OS X stores the certificates in the `/Library/Keychains/applepushserviced` keychain.

To ensure only the push certificate is in this keychain, delete the applepushserviced keychain, so it activates and creates a new keychain entry. You may try without this step, but if the keychain has other entries, the following steps may fail.

    sudo rm /Library/Keychains/applepushserviced.keychain
    sudo killall applepushserviced

This step extracts the push private key and certificate from the keychain. You may have to click *allow* on some keychain dialog during the process. First the private key:

    cd setup/mac
    ./compile-extract-private-key.sh
    python calculate-keychain-password.py > push-private.pem

This should output an RSA private key into `setup/mac/push-private.pem` in PEM form, like:

    -----BEGIN RSA PRIVATE KEY-----
    ... lots of characters ...
    -----END RSA PRIVATE KEY-----

Now extract the public key using Keychain Access. You can just drag `/Library/Keychains/applepushserviced.keychain` onto the Keychain Access icon, select the certificate with a UUID as name and export it as PEM. Copy this UUID, you will need it later to name the certificate file. Make sure not to try exporting the private key instead, this will not work.

Now that you have both private and public key in PEM encoding, place both in one file, first the private key and behind it public key. Move this file to `certs/device/<UUID>.pem` using the UUID you copied from Keychain Access before.

### DNS redirect(WiFi only)

The simplest way for redirecting a jailbroken iOS device or a Mac is modifying the `/etc/hosts` file. The following command will generate a hosts file for you. It may generate a few entries too much, but that shouldn't hurt.

    python setup/generate-hosts-file.py <server ip> > hosts

You obviously need to copy the generated hosts file to your device.

Make sure your device doesn't have network access via a phone network. In this case iOS ignores the `/etc/hosts` file and uses your carrier's DNS instead. **Disabling mobile data** should do the trick.

### Redirect via push daemon patch(WiFi+3G)

This method modifies the push daemons(apsd on iOS, applepushserviced on OS X) and replaces the string `push.apple.com` with a 14-character domain name of your choice.

#### Preparation: DNS Setup

You need two DNS entries, one wildcard A-record and a TXT record.

First, you have to choose a domain name. It must be exactly **14 characters** long like `push.apple.com`, so e.g. `ps.example.com` would work. (You could probably also use a shorter name and fill the remaining space with zero-bytes, but I haven't tried that).

The first DNS entry should be a **wildcard A-record** pointing to your servers IP, like `*.ps.example.com`.

An additional TXT record is used probably for determining the number of push domains the devices choose from. I set it to the same value `50` push.apple.com uses, but another one might also work. The content of this **TXT record** should look like ``"count=50"``.

You can verify your DNS setup using `dig`, it should show a similar answer for your server like it does for Apple's:

    dig -t TXT push.apple.com

#### iOS apsd patch

This step assumes you have a codesign certificate in your keychain named `iPhone Developer`, if you prefer another name you can change `patch-apsd.sh`. You also need `ldid` on your iOS device, I'm note sure whether it comes with Cydia by default.

    cd pushproxy
    setup/ios/patch-apsd.sh <device hostname> <14-char DNS entry>

You can find instructions on how to do this manually in `doc/howto-patch-apsd.md`

#### OS X applepushserviced patch

Like the iOS patch step, this step assumes there is a codesign certificate in your keychain named `iPhone Developer`.

    cd pushproxy
    setup/osx/patch-applepushserviced <14-char DNS entry>

This modifies `/System/Library/PrivateFrameworks/ApplePushService.framework/applepushserviced` and place a backup in the same directory named `applepushserviced.orig`.

After a restart the `applepushserviced` would request a new certificate from Apple since the binary has a new signature, so Keychain doesn't allow it to access the old certificate. So just do the 'Extract OS X Certificates' step which includes a restart anyway.

## Running

    cd src
    ./runpush.sh

This should be enough for most cases, if you want it to run as daemon and write output to a logfile in `data/`, create an empty file in src:

    touch production

If you want to change some configuration, just edit `pushserver.py.

## API

### Send notifications

PushProxy offers a [Twisted Perspective Broker](http://twistedmatrix.com/documents/current/core/howto/pb-usage.html) API for sending push notification directly to connected devices. It has the following signature:

    remote_sendNotification(self, pushToken, topic, payload)

It doesn't implement the store part of the store-and-forward architecture Apple's push notifiction system implements, so notifications sent via this API for will be lost for offline devices.

See `src/icl0ud/push/notification_sender.py` for the implementation.

### Message handler

You can subclass `icl0ud.push.dispatch.BaseHandler`, look at `dispatch.py`, `pushtoken_handler.py` and `notification_sender.py` in `src/icl0ud/push`.

Handlers can be configured in `src/pushserver.py`

## Debugging

Apple provides a [document](http://developer.apple.com/library/ios/#technotes/tn2265/_index.html) on debugging push connections. Especially useful are their instructions on how to enable debug logging on iOS and OS X. You can find the download link to the configuration file for iOS in the upper right corner of the page.

## Contributors

* Michael Frister
* Martin Kreichgauer
