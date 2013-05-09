# iOS 5 and OS X 10.6 and 10.7 Setup

iOS 5 and OS X before 10.8 didn't use the configuration from init-p01st.apple.com to determine which push server to connect to.

### Create CA and issue certificates

Note: This certificate creation only works for WiFi connections, see below if you want the proxy to work via 3G.

You need to create a SSL server certificate and install it on your device. It's common name should be:

    courier.push.apple.com

Then place the certificate in PEM encoding at the following path:

    certs/courier.push.apple.com/server.pem

### DNS redirect(WiFi only)

The simplest way for redirecting a jailbroken iOS device or a Mac is modifying the `/etc/hosts` file. The following command will generate a hosts file for you. It may generate a few entries too much, but that shouldn't hurt.

    python setup/generate-hosts-file-ios5.py <server ip> > hosts

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

This step assumes you have a codesign certificate in your keychain named `iPhone Developer`, if you prefer another name you can change `patch-apsd.sh`. You also need `ldid` on your iOS device, I'm not sure whether it comes with Cydia by default.

    cd pushproxy
    setup/ios/patch-apsd.sh <device hostname> <14-char DNS entry>

You can find instructions on how to do this manually in `doc/howto-patch-apsd.md`

#### OS X applepushserviced patch

Like the iOS patch step, this step assumes there is a codesign certificate in your keychain named `iPhone Developer`.

    cd pushproxy
    setup/osx/patch-applepushserviced <14-char DNS entry>

This modifies `/System/Library/PrivateFrameworks/ApplePushService.framework/applepushserviced` and place a backup in the same directory named `applepushserviced.orig`.

After a restart the `applepushserviced` would request a new certificate from Apple since the binary has a new signature, so Keychain doesn't allow it to access the old certificate. So just do the 'Extract OS X Certificates' step which includes a restart anyway.