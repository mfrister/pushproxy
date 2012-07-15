# Apple Push Service Protocol
iOS5/OS X 10.7

Starting from **iOS5**, iOS devices use a **new push protocol**. Besides iOS devices, **Mac** computers also use this push protocol to connect to Apple, e.g. for automated iTunes downloads or iCloud changes.

While the old iOS 4.x protocol uses message types [`00` to `06`](http://ios-rev.tumblr.com/post/7727869991/apple-push-service-protocol), the new protocol uses message types `07` to `0d`. The new protocol is more structured, i.e. all commands and fields have the following **type-length-value** encoding.

## Message Structure
* 1-byte **message type**
* 4-byte **payload length**
* **fields** (any number of occurences, also multiple per type)
    * 1-byte **field type** - meaning depends on message type
    * 2-byte **length of field value**
    * **field value**

### Example Message
Example *Connect* message

* `07` message type
* `00 00 00 27` payload length: 39 byte
* `01` field
    * `00 20` value length: 32 byte
    * `8b 88 72 36 9f 73 48 77 98 2d 39 f3 e2 5a 58 f5 45 9f de ba 8f 91 40 7e 87 0c 65 46 fe 20 f1 b1` value
* `02` field
    `00 01` value length: 1 byte
    `01` value</pre>

## Messages
### 07 Connect
* Device -> Server
* `07` message type
* fields
    * `01`: push token(optional)
        * 32-byte push token
        * at least once the server closed the connection upon receiving a message containing a push token and sending a 08 response
    * `02`: unknown
        * value: `01`
* begin of conversation

### 08 Connect Response
* Server -> Device
* `08` message type
* fields
    * `01`: status
        * observed values:
            * `00`: ok
            * `02`: some error, happened when device sent push token in *Connect* message, server closed connection after this message with this status
    * `04`: unknown
        * value: `10 00`
    * `05`: unknown
        * data: `00 02`
    * `03`: push token (optional)
        * 32-byte push token
        * actually sent after `05` field
* answer to *Connect* message, first data from server

### 09 Push Topics
* Device -> Server
* `09` message type
* fields
    * `02`: enabled topic(repeated)
        * 20-byte id
        * e.g. topic for an push-enabled app or a specific iCloud service like Find My iPhone
    * `03`: disabled topic(repeated)
        * 20-byte id like field `02`
        * not sure what disabled means and why disabled topics are sent to the server anyway
* sent to server several times in one session, first time directly after *Connect Response*

### 0a Push Notification
* Server -> Device
* iMessage: also Device -> Server
    * possibly also for other services, e.g. Find My Friends
* `0a` message type
* fields
    * `01`: recipient push token
        * push token like in *Connect/Connect Response* in case of app push notifications
        * iMessage topic in case of iMessage originating from Device
    * `02`: topic
        * see *Push Topics* message
    * `03`: payload
        * notification payload, e.g.
            * app notification: JSON, see Apple Developer Docs
            * iMessage: binary plist
    * `04`: response token
        * probably some unique id per notification to confirm delivery
        * returned in *Push Notification Response* message
    * `05`: expires
        * 32-bit UNIX timestamp
        * probably expiration time
    * `06` timestamp
        * 64-bit UNIX timestamp in nanoseconds
        * time when the notification was sent
        * divide by 10^9 to get standard UNIX timestamp in seconds (might result in decimal places)
    * `07`: unknown
        * observed value: `00`

### 0b Push Notification Response
* Server -> Device
* iMessage: also Device -> Server, see *Push Notification*
* `08` message type
* fields
    * `04` response token
        * same as in *Push Notification* this message responds to
    * `08` status?
        * observed values
            * `00`: ok
            * `02`: error?

### 0c Keep-Alive
* Device -> Server
* `0c` message type
* fields
    * `01`: connection method
        * e.g. "WiFi", "31038" for AT&T
        * WiFi/Numeric GSM Mobile Operator Code/Mobile Networc Code(MNC)
    * `02`: iOS version
        * e.g. "5.0"
    * `03`: iOS build number
        * e.g. "9A5220p"
    * `04`: device model
        * e.g. "iPhone2,1"
    * `05`: unknown
        * e.g. values like `10`, `15` or `20`
* keep-alive message, sent every 15-20 minutes

### 0d Command - keep-alive confirmation
* Server -> Device
* `0d` message type
* fields
    * none observed
* answer to *Keep-Alive* message, confirms keep-alive

### 0e Command - NoStorage

* Server -> Device
* `0e` message type
* fields
    * destination: push token as in Connect and Connect Response messages
* Note: Appeared in 10.8, unknown purpose

## Note

Mac OS X' push notification is slightly more complicated since it supports multiple users. For example the device sends multiple *Connect* messages, one for the system and one for each user, each with a different push token. This needs to be analyzed further.

