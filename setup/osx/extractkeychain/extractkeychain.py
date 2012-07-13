#!/usr/bin/python

# This program will dump the secrets out of an Apple keychain. Obviously you
# need to know the keychain's password - the keychain format seems quite
# secure. To avoid having to parse the keychain files too extensively, Apple's
# "security" commandline utility is executed. Unfortunately this means that
# this program really only works on OS X (or you could modify it to accept the
# output of "security dump-keychain" as input).

# Beware that this program makes no attempts to avoid swapping memory or
# clearing memory after use.

# Details for this were gleaned from looking at Apple's Security-177
# package (www.opensource.apple.com), and looking at some raw keychain files,
# with appropriate debugging statements added to a modifed Security.framework

# (c) 2004 Matt Johnston <matt @ ucc asn au>
# This code may be freely used and modified for any purpose.

# How it works:
#
# The parts of the keychain we're interested in are "blobs" (see ssblob.h in
# Apple's code). There are two types - DbBlobs and KeyBlobs.
#
# Each blob starts with the magic hex string FA DE 07 11 - so we search for
# that. There's only one DbBlob (at the end of the file), and that contains the
# file encryption key (amongst other things), encrypted with the master key.
# The master key is derived purely from the user's password, and a salt, also
# found in the DbBlob. PKCS #5 2 pbkdf2 is used for deriving the master key.
#
# Once we have the file encryption key, we can get the keys for each item. Each
# item is identified by a 20-byte label, starting with 'ssgp' (at least for
# normal items). The KeyBlob has the item encryption key encrypted with the
# file encryption key which we extracted earlier. Note that the Key encryption
# key has been further wrapped using the file encryption key, but a different
# IV (magicCmsIV), so we unencrypt it, reverse some bytes (woo magic, see
# perhaps rfc2630), then unencrypt it again, this time using the IV in the
# KeyBlob. (see getitemkey() for the details)
#
# Once we've got the map of labels->keys, we just parse the "security
# dump-keychain -r" output, and replace the raw ciphertext with what we decrypt
# using the item keys.

from sys import argv, exit, stdout, stderr
from string import split

from struct import unpack
from binascii import hexlify, unhexlify
from popen2 import popen4
from os.path import realpath
from getpass import getpass

from pbkdf2 import pbkdf2

from pyDes import triple_des, CBC

# If you want to use pycrypto (which is faster but requires a package to be
# installed and compiled), swap pyDes for pycrypto, here and in the
# kcdecrypt() function

# from Crypto.Cipher import DES3


keys = {}

dbkey = ""
dbblobpos = -1

magic = unhexlify( 'fade0711' )

magicCmsIV = unhexlify( '4adda22c79e82105' )


SALTLEN = 20
KEYLEN = 24
IVLEN = 8
LABELLEN = 20
BLOCKSIZE = 8

def getitemkeys( f ):

	f.seek(0)


	while f.tell() < dbblobpos: # we stop at the dbblob, since that's last

		str = f.read(4)
		if not str or len(str) == 0:
			# eof
			break
		if str == magic:
			getitemkey( f )


# gets a single key
def getitemkey( f ):
	global keys

#   0 0xfade0711 - magic number
#   4 version
#   8 crypto-offset - offset of the interesting data
#  12 total len
#  16 iv (8 bytes)
#  24 CSSM header (large, we don't care)
#  ... stuff here not used for now
# 156 the name of the key (ends null-terminated, there's probably another way
#     to figure the length, we don't care)
#  ...
# ??? 'ssgp................' - 20 byte label, starting with 'ssgp'. Use this
#     to match up the later record - this is at totallen + 8

	pos = f.tell() - 4

	# IV
	f.seek( pos + 16 )
	iv = f.read( IVLEN )

	# total len
	f.seek( pos + 12 )
	str = f.read(4)
	totallen = unpack(">I", str)[0]

	# label
	f.seek( pos + totallen + 8 )
	label = f.read( LABELLEN )

	if label[0:4] == 'SYSK':
		# don't care about system keys
		return

	if label[0:4] != 'ssgp':
		# TODO - we mightn't care about this, but warn during testing
		print "Unknown label %s after %d" % ( hexlify(label), pos)

	# ciphertext offset
	f.seek( pos + 8 )
	str = f.read(4)
	cipheroff = unpack(">I", str)[0]

	cipherlen = totallen - cipheroff
	if cipherlen % BLOCKSIZE != 0:
		raise "Bad ciphertext len after %d" % pos

	# ciphertext
	f.seek( pos + cipheroff )
	ciphertext = f.read( cipherlen )
	import pdb; pdb.set_trace()


	# we're unwrapping it, so there's a magic IV we use.
	plain = kcdecrypt( dbkey, magicCmsIV, ciphertext )

	# now we handle the unwrapping. we need to take the first 32 bytes,
	# and reverse them.
	revplain = ''
	for i in range(32):
		revplain += plain[31-i]

	# now the real key gets found. */
	plain = kcdecrypt( dbkey, iv, revplain )

	itemkey = plain[4:]

	if len(itemkey) != KEYLEN:
		raise Exception("Bad decrypted keylen!")

	keys[label] = itemkey


def getdbkey( f, pw ):
	global dbblobpos, dbkey

# DbBlob format:
#   The offsets from the start of the blob are as follows:
#   0 0xfade0711 - magic number
#   4 version
#   8 crypto-offset - offset of the encryption and signing key
#  12 total len
#  16 signature (16 bytes)
#  32 sequence
#  36 idletimeout
#  40 lockonsleep flag
#  44 salt (20 bytes)
#  64 iv (8 bytes)
#  72 blob signature (20)

	f.seek(-4, 2)

	while 1:
		f.seek(-8, 1) # back 4
		str = f.read(4)

		if not str or len(str) == 0:
			print>>stderr, "Couldn't find db key. Is a keychain file?"
			exit(1)

		if str == magic:
			break

	pos = f.tell() - 4
	dbblobpos = pos

	# ciphertext offset
	f.seek( pos + 8 )
	str = f.read(4)
	cipheroff = unpack(">I", str)[0]

	# salt
	f.seek( pos + 44 )
	salt = f.read( SALTLEN )

	# IV
	f.seek( pos + 64 )
	iv = f.read( IVLEN )

	# ciphertext
	f.seek( pos + cipheroff )
	ciphertext = f.read( 48 )


	# derive the key
	master = pbkdf2( pw, salt, 1000, KEYLEN )

	# decrypt the key
	plain = kcdecrypt( master, iv, ciphertext )

	dbkey = plain[0:KEYLEN]

	return dbkey
	# and now we're done


def kcdecrypt( key, iv, data ):

	if len(data) % BLOCKSIZE != 0:
		raise "Bad decryption data len isn't a blocksize multiple"

	cipher = triple_des( key, CBC, iv )
	# the line below is for pycrypto instead
	#cipher = DES3.new( key, DES3.MODE_CBC, iv )

	plain = cipher.decrypt( data )

	# now check padding
	pad = ord(plain[-1])
	if pad > 8:
		print>>stderr, "Bad padding byte. You probably have a wrong password"
		exit(1)

	for z in plain[-pad:]:
		if ord(z) != pad:
			print>>stderr, "Bad padding. You probably have a wrong password"
			exit(1)

	plain = plain[:-pad]

	return plain

def parseinput( kcfile ):

	# For some reason 'security dump-keychain' fails with non-absolute paths
	# sometimes.
	realfile = realpath( kcfile )
	cmd = 'security dump-keychain -r "%s"' % realfile

	progpipe = popen4( cmd )

	if not progpipe:
		print>>stderr, "Failed to run command '%s'" % cmd

	p = progpipe[0]

	while 1:
		l = p.readline()
		if not l:
			# EOF
			break


		if len(l) < 9:
			stdout.write( l )
			continue

		if l[0:9] == "raw data:":
			continue

		if l[0:2] != '0x':
			stdout.write( l )
			continue

		# it was some encrypted data, we get the hex format
		hexdata = split(l)[0][2:]

		data = unhexlify( hexdata )

		# format is
		# LABEL || IV || CIPHERTEXT
		# LABEL is 20 bytes, 'ssgp....'
		# IV is 8 bytes
		# CIPHERTEXT is a multiple of blocklen

		if len(data) < LABELLEN + IVLEN + BLOCKSIZE:
			stdout.write( "Couldn't decrypt data - malformed?\n" )
			continue

		label = data[0:LABELLEN]
		iv = data[LABELLEN:LABELLEN+IVLEN]
		ciphertext = data[LABELLEN+IVLEN:]

		if len(ciphertext) % BLOCKSIZE != 0:
			stdout.write( "Couldn't decrypt data - bad ciphertext len\n" )
			continue

		if not keys.has_key( label ):
			stdout.write( "Couldn't find matching decryption key\n" )
			continue

		key = keys[ label ]

		plaintext = kcdecrypt( key, iv, ciphertext )

		stdout.write( "decrypted secret:\n%s\n" % plaintext)

	return


def main():

	if len(argv) != 2:
		print>>stderr, "Usage: extractkeychain <keychain file>"
		exit(1)

	kcfile = argv[1]

	try:
		f = open(kcfile, "r")
	except IOError, e:
		print>>stderr, e
		exit(1)

	print "This will dump keychain items _and secrets_ to standard output."

	pw = getpass( "Keychain password: " )

	getdbkey( f, pw )

	getitemkeys( f )
	parseinput( kcfile )

if __name__ == '__main__':
	main()
