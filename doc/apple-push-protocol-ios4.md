Apple Push Service Protocol - iOS4.3.3
======================================

iOS devices connect to Apple's push servers via **port 5223**. The protocol has nothing to do with XMPP which used to establish SSL-encrypted client connections to this port. The Push service protocol also uses SSL encryption. While the protocol seems **proprietary**, client authentication happens using **SSL client certificates**. These client certificates are issued to the device during activation via iTunes and stored in a keychain.

The protocol uses a **Type-Length-Value** encoding, while sometimes the length is omitted and thus seems to be defined implicitly through the Type. Each of the **seven message types** has a one-byte type. The messages are outlined below.

00 Device Hello
-----------------------
* Structure
    * `00` command
    * 4-Byte size (always `00 20`/32 Byte)
    * 32-Byte data - some device id? - seems to be different from UDID
* begin of conversation

01 Server Hello
-----------------------
* Structure
    * `01` command
    * 4 unknown Bytes (were always `00 00 00 00`)
    * one of the following
        * 1-Byte size `00`
        * 1-Byte size `20` followed by 32 Byte "Push Token"
            * sent via HTTP Header when registering on `https://registration.ess.apple.com/WebObjects/VCRegistrationService.woa/wa/register`


02 Push Application IDs
-------------------------------
* Structure
    * `02` Command
    * two lists containing 20-Byte Strings
        * begin with 4-Byte item count and 4-Byte item size(always `14`/20)
* seems to send list of Push-enabled Applications to Apple
    * one list for Apps with enabled push notifications, one for disabled?
* 19 Entries, sometimes in different lists
* 16 Push Apps shown in Settings.app + 3 iOS services?
    * at least 3 were in the first list of all messages
        * one of them is a string received together with Find-My-iPhone Push Notifications

03 Push Notification
----------------------------
* Server -> Device
* Structure
    * `03` Command
    * 4-Byte size (always `14`/20)
    * 20 Bytes Data
        * App ID for Push Notifications, appears in list of `03` messages
  * 4-Byte size
  * Data, Push Notification in JSON Format
* sample JSON from Prowl App(reformatted, XXX was unknown integer like 100123456)
<pre>{
    "urlhint":"XXX",
    "aps":
    {
        "badge":1,
        "sound":"elysium.caf",
        "alert":"2Prowl—Website\nhttps://localhost:8080/"
    }
}</pre>
* Requests from Find-My-iPhone are also issued as Push Notifications

04 Push Notification Confirmation
-----------------------------------------
* Device -> Server
* Structure
  * `04` Command
  * 3 unkown Bytes (were always `00 00 00`)
* confirms push notifications

05 Keep-Alive?
----------------------
* Device -> Server
* Structure
    * `05` Command
    * 4-Byte length(e.g. `1B`/27)
    * Data, e.g.: `WiFi 4.3.3 8J2 iPhone2,1 17`
        * what does 17 mean?
* seems to be keep-alive message, sent periodically
* confirmed by server with `06` Command (1-Byte)

06 Keep-Alive Answer
----------------------------
* Server -> Device
* Structure
  * `06` Command
* confirms command `05`
