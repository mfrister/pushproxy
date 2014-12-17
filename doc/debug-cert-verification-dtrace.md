# Debugging OS X certificate verification errors with DTrace

When trying to find out, why the OS X push daemon (apsd) doesn't connect to [pushproxy](https://github.com/meeee/pushproxy) on 10.10, I found that the [apsd debug logging](http://developer.apple.com/library/ios/#technotes/tn2265/_index.html) doesn't output very useful information for determining why it sees a server certificate as invalid.

The log only contains error codes returned by [`SecTrustEvaluate`](https://developer.apple.com/library/ios/documentation/Security/Reference/certifkeytrustservices/index.html#//apple_ref/c/func/SecTrustEvaluate) ([`SecTrustResultType`](https://developer.apple.com/library/ios/documentation/Security/Reference/certifkeytrustservices/index.html#//apple_ref/c/tdef/SecTrustResultType) values) that are not very helpful and significantly boiled down (see Trust::diagnoseOutcome() in [Trust.cpp](https://opensource.apple.com/source/Security/Security-57031.1.35/Security/include/security_keychain/Trust.cpp)) from the errors that are generated when verifying the certificate chain. Such a value could be `kSecTrustResultRecoverableTrustFailure`, which doesn't tell you why the verification failed.

Fortunately, the Security framework, which does certificate verification on OS X, includes a DTrace probe that allows access to debug messages. The following script outputs debug messages for all processes using the framework.

```d
security_debug*:Security:secdebug_internal:log /copyinstr(arg0) != "cmutex"/ {
    printf("%s %s %s", execname, copyinstr(arg0), copyinstr(arg1))
}
```

Here's the script in a single line, ready for use:

    sudo dtrace -n 'security_debug*:Security:secdebug_internal:log /copyinstr(arg0) != "cmutex"/ { printf("%s %s %s", execname, copyinstr(arg0), copyinstr(arg1)) }'

The script outputs the process pid, the probe name, the executable name (apsd in the following example), a scope and the debug message. The predicate `/copyinstr(arg0) != "cmutex"/` excludes messages with the 'cmutex' scope, which are quite a lot and not interesting for certificate verification.

If you want to limit the output to a specific process, specify it's PID in place of the `*` in `security_debug*:`, e.g. `security_debug1234:`.

Output looks like this:

      1   3757            secdebug_internal:log apsd tpDbDebug tpDbFindIssuer: returning record 0x7fee11d0f010
      1   3757            secdebug_internal:log apsd tpDebug buildCertGroup: Cert FOUND in dbList
      1   3757            secdebug_internal:log apsd trustSettingsEval tsCheckPolicy: policy mismatch
      1   3757            secdebug_internal:log apsd trustSettingsEval evaluateCert: MATCH
      1   3757            secdebug_internal:log apsd trustSettings SecTrustSettingsEvaluateCert: found in domain 1
      1   3757            secdebug_internal:log apsd tpTrustSettings Trust[As]Root found
      1   3757            secdebug_internal:log apsd tpPolicy tpCompareHostNames: wildcard mismatch (2)
     [...]
      1   3757            secdebug_internal:log apsd trusteval certGroupVerify exception: -2147408896

The messages are not too easily understandable, often you'll have to search for the  message in the [Security framework's source](https://opensource.apple.com/source/Security/Security-57031.1.35/) to understand the context.

One helpful message though, is the `trusteval certGroupVerify exception: <number>` message. It contains a number that refers to an error that provides a pretty specific description. `-2147408896` in the example above is a 'Host name mismatch (`CSSMERR_APPLETP_HOSTNAME_MISMATCH`)' error.

The error descriptions can be found in `cssmerr.h`,  `cssmapple.h` and possibly other files. I added two lists of such errors to pushproxy: [debug-cert-verification-dtrace.md](https://github.com/meeee/pushproxy/blob/master/doc/debug-cert-verification-dtrace.md#errors).

In this case, you can find out even more than the error code says by looking at the messages above. The message `tpCompareHostNames: wildcard mismatch (2)` tells you which specific check failed, searching for it reveals the `tpCompareHostNames` method in `certGroupUtils.cpp`.

## Errors

* `-2147409663`: `CSSMERR_TP_INVALID_CALLERAUTH_CONTEXT_POINTER`
* `-2147409662`: `CSSMERR_TP_INVALID_IDENTIFIER_POINTER`
* `-2147409661`: `CSSMERR_TP_INVALID_KEYCACHE_HANDLE`
* `-2147409660`: `CSSMERR_TP_INVALID_CERTGROUP`
* `-2147409659`: `CSSMERR_TP_INVALID_CRLGROUP`
* `-2147409658`: `CSSMERR_TP_INVALID_CRLGROUP_POINTER`
* `-2147409657`: `CSSMERR_TP_AUTHENTICATION_FAILED`
* `-2147409656`: `CSSMERR_TP_CERTGROUP_INCOMPLETE`
* `-2147409655`: `CSSMERR_TP_CERTIFICATE_CANT_OPERATE`
* `-2147409654`: `CSSMERR_TP_CERT_EXPIRED`
* `-2147409653`: `CSSMERR_TP_CERT_NOT_VALID_YET`
* `-2147409652`: `CSSMERR_TP_CERT_REVOKED`
* `-2147409651`: `CSSMERR_TP_CERT_SUSPENDED`
* `-2147409650`: `CSSMERR_TP_INSUFFICIENT_CREDENTIALS`
* `-2147409649`: `CSSMERR_TP_INVALID_ACTION`
* `-2147409648`: `CSSMERR_TP_INVALID_ACTION_DATA`
* `-2147409646`: `CSSMERR_TP_INVALID_ANCHOR_CERT`
* `-2147409645`: `CSSMERR_TP_INVALID_AUTHORITY`
* `-2147409644`: `CSSMERR_TP_VERIFY_ACTION_FAILED`
* `-2147409643`: `CSSMERR_TP_INVALID_CERTIFICATE`
* `-2147409642`: `CSSMERR_TP_INVALID_CERT_AUTHORITY`
* `-2147409641`: `CSSMERR_TP_INVALID_CRL_AUTHORITY`
* `-2147409640`: `CSSMERR_TP_INVALID_CRL_ENCODING`
* `-2147409639`: `CSSMERR_TP_INVALID_CRL_TYPE`
* `-2147409638`: `CSSMERR_TP_INVALID_CRL`
* `-2147409637`: `CSSMERR_TP_INVALID_FORM_TYPE`
* `-2147409636`: `CSSMERR_TP_INVALID_ID`
* `-2147409635`: `CSSMERR_TP_INVALID_IDENTIFIER`
* `-2147409634`: `CSSMERR_TP_INVALID_INDEX`
* `-2147409633`: `CSSMERR_TP_INVALID_NAME`
* `-2147409632`: `CSSMERR_TP_INVALID_POLICY_IDENTIFIERS`
* `-2147409631`: `CSSMERR_TP_INVALID_TIMESTRING`
* `-2147409630`: `CSSMERR_TP_INVALID_REASON`
* `-2147409629`: `CSSMERR_TP_INVALID_REQUEST_INPUTS`
* `-2147409628`: `CSSMERR_TP_INVALID_RESPONSE_VECTOR`
* `-2147409627`: `CSSMERR_TP_INVALID_SIGNATURE`
* `-2147409626`: `CSSMERR_TP_INVALID_STOP_ON_POLICY`
* `-2147409625`: `CSSMERR_TP_INVALID_CALLBACK`
* `-2147409624`: `CSSMERR_TP_INVALID_TUPLE`
* `-2147409623`: `CSSMERR_TP_NOT_SIGNER`
* `-2147409622`: `CSSMERR_TP_NOT_TRUSTED`
* `-2147409621`: `CSSMERR_TP_NO_DEFAULT_AUTHORITY`
* `-2147409620`: `CSSMERR_TP_REJECTED_FORM`
* `-2147409619`: `CSSMERR_TP_REQUEST_LOST`
* `-2147409618`: `CSSMERR_TP_REQUEST_REJECTED`
* `-2147409617`: `CSSMERR_TP_UNSUPPORTED_ADDR_TYPE`
* `-2147409616`: `CSSMERR_TP_UNSUPPORTED_SERVICE`
* `-2147409615`: `CSSMERR_TP_INVALID_TUPLEGROUP_POINTER`
* `-2147409614`: `CSSMERR_TP_INVALID_TUPLEGROUP`

### Apple 'custom' errors

More errors ('custom' Apple errors, but 'custom' probably relates to some implementation detail of the security framework):

* `-2147408896`: Host name mismatch (`CSSMERR_APPLETP_HOSTNAME_MISMATCH`)
* `-2147408895`: Non-understood extension with Critical flag true (`CSSMERR_APPLETP_UNKNOWN_CRITICAL_EXTEN`)
* `-2147408894`: Basic Constraints extension required per policy, but not present (`CSSMERR_APPLETP_NO_BASIC_CONSTRAINTS`)
* `-2147408893`: Invalid BasicConstraints.CA (`CSSMERR_APPLETP_INVALID_CA`)
* `-2147408892`: Invalid Authority Key ID (`CSSMERR_APPLETP_INVALID_AUTHORITY_ID`)
* `-2147408891`: Invalid Subject Key ID (`CSSMERR_APPLETP_INVALID_SUBJECT_ID`)
* `-2147408890`: Invalid Key Usage for policy (`CSSMERR_APPLETP_INVALID_KEY_USAGE`)
* `-2147408889`: Invalid Extended Key Usage for policy (`CSSMERR_APPLETP_INVALID_EXTENDED_KEY_USAGE`)
* `-2147408888`: Invalid Subject/Authority Key ID Linkage (`CSSMERR_APPLETP_INVALID_ID_LINKAGE`)
* `-2147408887`: PathLengthConstraint exceeded (`CSSMERR_APPLETP_PATH_LEN_CONSTRAINT`)
* `-2147408886`: Cert group terminated at a root cert which did not self-verify (`CSSMERR_APPLETP_INVALID_ROOT`)
* `-2147408885`: CRL expired/not valid yet (`CSSMERR_APPLETP_CRL_EXPIRED`)
* `-2147408884`: CSSMERR_APPLETP_CRL_NOT_VALID_YET (`CSSMERR_APPLETP_CRL_NOT_VALID_YET`)
* `-2147408883`: Cannot find appropriate CRL (`CSSMERR_APPLETP_CRL_NOT_FOUND`)
* `-2147408882`: specified CRL server down (`CSSMERR_APPLETP_CRL_SERVER_DOWN`)
* `-2147408881`: illegible CRL distribution point URL (`CSSMERR_APPLETP_CRL_BAD_URI`)
* `-2147408880`: Unknown critical cert/CRL extension (`CSSMERR_APPLETP_UNKNOWN_CERT_EXTEN`)
* `-2147408879`: CSSMERR_APPLETP_UNKNOWN_CRL_EXTEN (`CSSMERR_APPLETP_UNKNOWN_CRL_EXTEN`)
* `-2147408878`: CRL not verifiable to anchor or root (`CSSMERR_APPLETP_CRL_NOT_TRUSTED`)
* `-2147408877`: CRL verified to untrusted root (`CSSMERR_APPLETP_CRL_INVALID_ANCHOR_CERT`)
* `-2147408876`: CRL failed policy verification (`CSSMERR_APPLETP_CRL_POLICY_FAIL`)
* `-2147408875`: IssuingDistributionPoint extension violation (`CSSMERR_APPLETP_IDP_FAIL`)
* `-2147408874`: Cert not found at specified issuerAltName (`CSSMERR_APPLETP_CERT_NOT_FOUND_FROM_ISSUER`)
* `-2147408873`: Bad cert obtained from specified issuerAltName (`CSSMERR_APPLETP_BAD_CERT_FROM_ISSUER`)
* `-2147408872`: S/MIME Email address mismatch (`CSSMERR_APPLETP_SMIME_EMAIL_ADDRS_NOT_FOUND`)
* `-2147408871`: Appropriate S/MIME ExtendedKeyUsage not found (`CSSMERR_APPLETP_SMIME_BAD_EXT_KEY_USE`)
* `-2147408870`: S/MIME KeyUsage incompatibility (`CSSMERR_APPLETP_SMIME_BAD_KEY_USE`)
* `-2147408869`: S/MIME, cert with KeyUsage flagged !critical (`CSSMERR_APPLETP_SMIME_KEYUSAGE_NOT_CRITICAL`)
* `-2147408868`: S/MIME, leaf with empty subject name and no email addrs in SubjectAltName (`CSSMERR_APPLETP_SMIME_NO_EMAIL_ADDRS`)
* `-2147408867`: S/MIME, leaf with empty subject name, SubjectAltName not critical (`CSSMERR_APPLETP_SMIME_SUBJ_ALT_NAME_NOT_CRIT`)
* `-2147408866`: Appropriate SSL ExtendedKeyUsage not found (`CSSMERR_APPLETP_SSL_BAD_EXT_KEY_USE`)
* `-2147408865`: unparseable OCSP response (`CSSMERR_APPLETP_OCSP_BAD_RESPONSE`)
* `-2147408864`: unparseable OCSP request (`CSSMERR_APPLETP_OCSP_BAD_REQUEST`)
* `-2147408863`: OCSP service unavailable (`CSSMERR_APPLETP_OCSP_UNAVAILABLE`)
* `-2147408862`: OCSP status: cert unrecognized (`CSSMERR_APPLETP_OCSP_STATUS_UNRECOGNIZED`)
* `-2147408861`: revocation check not successful for each cert (`CSSMERR_APPLETP_INCOMPLETE_REVOCATION_CHECK`)
* `-2147408860`: general network error (`CSSMERR_APPLETP_NETWORK_FAILURE`)
* `-2147408859`: OCSP response not verifiable to anchor or root (`CSSMERR_APPLETP_OCSP_NOT_TRUSTED`)
* `-2147408858`: OCSP response verified to untrusted root (`CSSMERR_APPLETP_OCSP_INVALID_ANCHOR_CERT`)
* `-2147408857`: OCSP response signature error (`CSSMERR_APPLETP_OCSP_SIG_ERROR`)
* `-2147408856`: No signer for OCSP response found (`CSSMERR_APPLETP_OCSP_NO_SIGNER`)
* `-2147408855`: OCSP responder status: malformed request (`CSSMERR_APPLETP_OCSP_RESP_MALFORMED_REQ`)
* `-2147408854`: OCSP responder status: internal error (`CSSMERR_APPLETP_OCSP_RESP_INTERNAL_ERR`)
* `-2147408853`: OCSP responder status: try later (`CSSMERR_APPLETP_OCSP_RESP_TRY_LATER`)
* `-2147408852`: OCSP responder status: signature required (`CSSMERR_APPLETP_OCSP_RESP_SIG_REQUIRED`)
* `-2147408851`: OCSP responder status: unauthorized (`CSSMERR_APPLETP_OCSP_RESP_UNAUTHORIZED`)
* `-2147408850`: OCSP response nonce did not match request (`CSSMERR_APPLETP_OCSP_NONCE_MISMATCH`)
* `-2147408849`: Illegal cert chain length for Code Signing  (`CSSMERR_APPLETP_CS_BAD_CERT_CHAIN_LENGTH`)
* `-2147408848`: Missing Basic Constraints for Code Signing (`CSSMERR_APPLETP_CS_NO_BASIC_CONSTRAINTS`)
* `-2147408847`: Bad PathLengthConstraint for Code Signing (`CSSMERR_APPLETP_CS_BAD_PATH_LENGTH`)
* `-2147408846`: Missing ExtendedKeyUsage for Code Signing (`CSSMERR_APPLETP_CS_NO_EXTENDED_KEY_USAGE`)
* `-2147408845`: Development style Code Signing Cert Detected (`CSSMERR_APPLETP_CODE_SIGN_DEVELOPMENT`)
* `-2147408844`: Illegal cert chain length for Resource Signing  (`CSSMERR_APPLETP_RS_BAD_CERT_CHAIN_LENGTH`)
* `-2147408843`: Bad extended key usage for Resource Signing (`CSSMERR_APPLETP_RS_BAD_EXTENDED_KEY_USAGE`)
* `-2147408842`: Trust Setting: deny (`CSSMERR_APPLETP_TRUST_SETTING_DENY`)
* `-2147408841`: Invalid empty SubjectName (`CSSMERR_APPLETP_INVALID_EMPTY_SUBJECT`)
* `-2147408840`: Unknown critical Qualified Cert Statement ID (`CSSMERR_APPLETP_UNKNOWN_QUAL_CERT_STATEMENT`)
* `-2147408839`: Missing required extension (`CSSMERR_APPLETP_MISSING_REQUIRED_EXTENSION`)
* `-2147408838`: Extended key usage not marked critical (`CSSMERR_APPLETP_EXT_KEYUSAGE_NOT_CRITICAL`)
* `-2147408837`: Required name or identifier not present (`CSSMERR_APPLETP_IDENTIFIER_MISSING`)
* `-2147408836`: Certificate authority pinning mismatch (`CSSMERR_APPLETP_CA_PIN_MISMATCH`)

