#include <CoreFoundation/CFData.h>
#include <CoreFoundation/CFString.h>
#include <Security/SecImportExport.h>
#include <Security/SecKeychain.h>
#include <Security/SecKeychainItem.h>
#include <stdio.h>
#include <string.h>


// compile: gcc extract-private-key.c -o extract-private-key -framework Security -framework CoreFoundation

int main(int argc, char * const *argv) {
    if(argc != 4) {
        printf("Usage: %s <keychain file> <hex keychain password> <output file>\n", argv[0]);
        exit(1);
    }
    char *name = argv[1];
    const char *password_hex = argv[2];
    const char *output_file = argv[3];

    if(strlen(password_hex) % 2 != 0) {
        printf("Odd hex password length. This must be even.\n");
        exit(1);
    }
    const uint password_length = strlen(password_hex)/2;
    char *password = malloc(password_length + 1);

    char *dst = password;
    char *end = password + password_length;
    unsigned int u;

    while (dst < end && sscanf(password_hex, "%2x", &u) == 1) {
        *dst++ = u;
        password_hex += 2;
    }
    *end = '\0';

    //char* name = "/Users/mf/src-me/Sammlung/xmpp-mitm/mac/keychain-analysis/applepushserviced-modified.keychain";
    printf("Unlocking '%s'...\n", name);
    SecKeychainRef keychain = NULL;
    OSStatus result;

    result = SecKeychainOpen(name, &keychain);
    if (result)
    {
        printf("SecKeyChainOpen: Error nr. %d", result);
    }

    result = SecKeychainUnlock(keychain, strlen(password), password, TRUE);
    if (result)
    {
        printf("SecKeychainUnlock: Error nr. %d\n", result);
    }
    SecKeychainStatus status;
    result = SecKeychainGetStatus(keychain, &status);
    printf("SecKeychainGetStatus returned: %i\n", result);

    printf("Keychain status: %u\n", status);
    if(status != 7) {
        printf("Keychain unlock failed.\n");
        exit(1);
    }

    SecKeychainSearchRef searchRef;
    result = SecKeychainSearchCreateFromAttributes(
                    keychain,
                    kSecPrivateKeyItemClass,
                    NULL,
                    &searchRef);
    printf("SecKeychainSearchCreateFromAttributes returned: %i\n", result);


    SecKeychainItemRef itemRef;
    result = SecKeychainSearchCopyNext(searchRef, &itemRef);
    printf("SecKeychainSearchCopyNext returned: %i\n", result);

    CFStringRef passphrase = CFStringCreateWithCString(NULL,
                                "passphrase",
                                kCFStringEncodingUTF8);

    const SecItemImportExportKeyParameters params = {
        0,
        0,
        passphrase,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL
    };

    CFDataRef exportedData;

    result = SecItemExport(itemRef,
                kSecFormatWrappedPKCS8,
                0,
                &params,
                &exportedData);
    printf("SecItemExport returned: %i\n", result);

    CFIndex length = CFDataGetLength(exportedData);
    printf("exportedData length: %2i\n", (uint)length);

    UInt8* data = (UInt8*)CFDataGetBytePtr(exportedData);
    printf("Private key: ");
    long i;
    for(i = 0; i < length; i++) {
        printf("%x", data[i]);
    }
    printf("\n");

    FILE* fh = fopen(output_file, "wb");
    fwrite(data, sizeof(UInt8), length, fh);
    fclose(fh);

    printf("Done.\n");
}



