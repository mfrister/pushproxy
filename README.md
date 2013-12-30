# PushProxy

PushProxy is a **man-in-the-middle proxy** for **iOS and OS X Push Notifications**. It decodes the push protocol and outputs messages in a readable form. It also provides APIs for handling messages and sending push notifications directly to devices without sending them via Apple's infrastructure.

For a reference on the push protocol, see [apple-push-protocol-ios5-lion.md](doc/apple-push-protocol-ios5-lion.md). iOS4 and earlier used another version of the protocol, described in [apple-push-protocol-ios4.md](doc/apple-push-protocol-ios4.md). This proxy only supports the iOS5 protocol.

I tested only using jailbroken iOS devices, but it may be possible to use a push certificate from a jailbroken device and use it to connect a non-jailbroken device to Apple's servers. At least some apps using push notifications will be confused if you do this, but I think this was a way for hacktivated iPhones to get a push certificate.

## 'Screenshot'

    2013-02-17 21:54:15+0100 [#0] New connection from 192.168.0.120:61321
    2013-02-17 21:54:15+0100 [#0] SSL handshake done: Device: B481816D-4650-49EA-977C-9FCBDEB30CB1
    2013-02-17 21:54:15+0100 [#0] Connecting to push server: 17.172.232.59:5223
    2013-02-17 21:54:15+0100 Starting factory <icl0ud.push.intercept.InterceptClientFactory instance at 0x147d5a8>
    2013-02-17 21:54:15+0100 [#0] -> APSConnect presenceFlags: 00000002 state: 01
                                       push token: 4b5543c35b48429bbe770a8af11457f39374bd4e43e94adaa86bd979c50bdb05
    2013-02-17 21:54:16+0100 [#0] <- APSConnectResponse 00 messageSize: 4096 unknown5: 0002
    2013-02-17 21:54:16+0100 [#0] -> APSTopics for token <none>
                                       enabled topics: 
                                         com.apple.itunesstored
                                         com.apple.madrid
                                         com.apple.mobileme.fmip
                                         com.apple.gamed
                                         com.apple.ess
                                         com.me.keyvalueservice
                                         4357ca2451b7b787caea8a603e51a1f45feaeda4
                                         com.apple.mobileme.fmf1
                                         com.apple.mediastream.subscription.push
                                       disabled topics:
                                         com.apple.store.Jolly
    2013-02-17 21:54:16+0100 [#0] -> APSKeepAlive 10min carrier: 31038 iPhone4,1/6.1.1/10B145
    2013-02-17 21:54:16+0100 [#0] <- APSKeepAliveResponse
    2013-02-17 22:10:04+0100 [#0] <- APSNotification 4357ca2451b7b787caea8a603e51a1f45feaeda4
                                       timestamp: 2013-02-17 22:10:16.642561 expiry: 1970-01-01 00:59:59
                                       messageId: 00000000                   storageFlags: 00
                                       unknown9:  None                       payload decoded (json)
                                       {u'aps': {u'alert': u'Chrome\u2014meeee/pushproxy \xb7 GitHub\nhttps://github.com/meeee/pushproxy',
                                                 u'badge': 3,
                                                 u'sound': u'elysium.caf'},
                                        u'urlhint': u'1234567'}
    2013-02-17 22:10:06+0100 [#0] -> APSNotificationResponse message: 00000000 status: 00

## Setup

### Overview

Setup on iOS >= 6.0 and OS X >= 10.8 requires several steps:

1. [Install pushproxy including dependencies](#install-pushproxy-and-dependencies)
2. [Create a CA and issue certificates](#create-ca-and-issue-certificates)
3. [Install CA on device](#install-ca-on-device)
4. [Extract and copy device certificate](#extract-and-copy-device-certificate)
5. [Create configuration bag](#create-configuration-bag)
6. [Redirect DNS](#redirect-dns)

You can find instructions on how to redirect the push connection on iOS < 6.0 and OS X < 10.8 in [setup-ios5-10.7.md](doc/setup-ios5-10.7.md).

### Install pushproxy and dependencies

The proxy is written in Python, I recommend setting up a virtualenv and installing the requirements:

    pip install -r src/requirements.txt

Setting up PushProxy requires redirecting push connections to your server and setting up X.509 certificates for SSL authentication.

The push protocol uses SSL for client and server authentication. You need to extract the device certificate and give it to the proxy so it can authenticate itself as device against Apple. You also need to make the device trust your proxy since you are impersonating Apple's servers.

### Create CA and issue certificates

Your device has to trust two certificates, so the easiest way is to create a CA and issue the certificates. This way you only need to install one CA certificate on the device.

The first hostname you need to create a SSL server certificate for:

    init-p01st.push.apple.com

You will need this certificate later to sign a configuration bag.

#### iOS <= 6, OS X <= 10.8

You can choose the hostname of the second certificate, the push hostname. When connecting to the push hostname (Apple's default is courier.push.apple.com), apsd prepends a random number to the hostname, perhaps for load balancing and/or fault tolerance (e.g. 22-courier.push.apple.com). You need to configure a DNS server which responds to these hostnames. You can use a wildcard subdomain to redirect all host names with different numbers to the proxy, like `*.push.example.com`. So in this case, you would create a certificate for:

    courier.push.example.com

Store the generated certificate and private key in PEM encoding at the following path:

    certs/courier.push.apple.com/server.pem


#### iOS 7, OS X 10.9

Beginning with OS X 10.9 and probably iOS 7 (untested), `apsd` does certificate pinning and checks the root certificate as well as chain length and some attributes of the leaf certificate. The root certificate contained in the `apsd` binary is replaced in a later step.

The certificate chain needs a length of 3, so you have to use a CA certificate as well as an additional intermediary CA certificate that signs the leaf.

Create the leaf certificate with the following attributes:

    * Common Name: courier.push.apple.com
    * Country Name: US
    * State/Province Name: California
    * Locality Name: Cupertino
    * Organization Name: Apple Inc.

Store the generated certificate, the intermediary CA certificate and the private key in PEM encoding at the following path:

    certs/courier.push.apple.com/server.pem


### Install CA on device

You can install the CA certificate on iOS devices via Safari or iPhone Configuration Utility.

On OS X you can use keychain access to install the certificate, make sure to install it in the System keychain, not your login keychain. Mark it as trusted, Keychain Access should then display it as 'marked as trusted for all users'.

### Patch apsd (OS X 10.9 and iOS 7 only)

This patch replaces the pinned root certificate in the `apsd` binary with a chosen one having the same or a shorter length than the original certificate.

You can run the script with the following command. When running the script, think about making a backup and make sure to restore permissions afterwards.

    setup/osx/patch_apsd.py <path to apsd> <new root CA cert> <code signing identity>

    <path to apsd>: Path to the apsd binary. Usually stored in `/System/Library/PrivateFrameworks/ApplePushService.framework/apsd`. You might need to copy it/change permissions to patch as a user.
    <new root ca cert>: Path to a root certificate in PEM form to replace the original root certificate by Entrust. This certificate must be no longer than 1120 bytes (length of the original certificate). Shorter is ok, the rest will be zero-padded and the certificate size will be adjusted in the code.
    <code signing identity>: Name of a code signing certificate understood by the `codesign` utility, make sure your machine trusts this cert (root)

Make sure to do this before extracting the device certificate. Once you replaced the `apsd` binary, the keychain will not allow the apsd daemon to use the existing keychain any more and returns the following or a similar error:

    The operation couldn’t be completed. (OSStatus error -25293.)

When you restart/run `apsd` afterwards (`kill` or `launchctl`), after a few failing attempts to access the keychain, apsd will request a new push certificate, which you can then extract as describe in the following section.

### Extract and copy device certificate
#### Extract iOS Certificates

First, download the [nimble](http://xs1.iphwn.org/releases/PushFix.zip) tool, extract `PushFix.zip` and place `nimble` into `setup/ios`. The following script will copy the tool to your iOS device, run it and copy the extracted certificates back to your computer. It assumes you have **SSH** running on your device. I recommend setting up key-based authentication, otherwise you will be typing your password a few times.

Make sure you are in the pushproxy root directory, otherwise the script will fail.

    cd pushproxy
    setup/ios/extract-and-convert-certs.sh root@<device hostname>

You can find the extracted certificates in `certs/device`. Both public and private key are in one PEM-file.

#### Extract OS X Certificates

Note: If you want to connect at least one device via a patched push daemon, you need to patch the push daemon on OS X first.

OS X stores the certificates in a keychain in `/Library/Keychains`, either in `applepushserviced.keychain` or in `apsd.keychain`.

This step extracts the push private key and certificate from the keychain. It stores them in `certs/device/<UUID>.pem`

    setup/osx/extract_certificate.py -f

You can remove the -f parameter to get key and certificate on stdout instead of writing them to a file.

### Create Configuration Bag

Since iOS 6 and OS X 10.8, apsd loads a signed configuration bag. This bag contains the push domain to connect to among a number of less interesting parameters.

Apple's original bag can be found here: [http://init-p01st.push.apple.com/bag](http://init-p01st.push.apple.com/bag) (Download)

Run the following command to create a bag for your own domain:

    setup/bag.py <push domain> <signing certificate> > bag

*push domain*: The domain apsd should connect to, e.g. `courier.push.example.com`. apsd then actually connects to this domain prepended with a random number between 1 and 50, e.g. 22-courier.push.example.com.

*signing certificate*: the previously created server certificate for `init-p01st.push.apple.com`. The script signs the bag using this certificate and includes it, so apsd can verify the signature.

You can either upload this bag to your own webserver or run the setup/bag.py command with a `-s` switch at the end. It starts a webserver on port 80, so you have to run the command as root. The webserver requires [flask](http://flask.pocoo.org/docs/), which can be installed via `pip install flask`.

### Redirect DNS

You can choose whatever method you want to redirect DNS, pushproxy includes a script to generate an `/etc/hosts` file. You can run it using the following command:

    setup/generate-hosts-file.py <webserver ip> > hosts

*webserver ip*: IP of your webserver that serves the configuration bag. apsd uses `init-p01st.push.apple.com` as HTTP host, so you can use a vhost for that domain if you want.

When apsd fails to load the configuration bag, it uses the old iOS 5/OS X 10.7 method as fallback. Thus the generate-hosts-file command redirects all these hosts to 127.0.0.1 to ensure apsd only connects to pushproxy.

You obviously need to copy the generated hosts file to the device.

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

The document is a bit outdated. If you want to enable debug logging on newer OS X versions like 10.8.2, you have to replace `applepushserviced` with `apsd` in the `defaults` and `killall` commands.

## Contributors

* Michael Frister
* Martin Kreichgauer

## Thanks

* [Matt Johnston](http://www.ucc.asn.au/~matt/apple/) for writing [extractkeychain](http://www.ucc.asn.au/~matt/src/extractkeychain-0.1.tar.gz) that is used for deriving the master key and decrypting keys from the OS X keychain
* Vladimir "Farcaller" Pouzanov for writing [python-bplist](https://github.com/farcaller/bplist-python) which is included and helps extracting the push private key from the OS X keychain

![pi](https://planb.frister.net/pi/piwik.php?idsite=3&rec=1)
