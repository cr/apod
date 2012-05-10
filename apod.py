#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##################################################################################################
# info
###
# apod - download the Astronomy Picture of the day
# (c) 2003-20012 Christiane Ruetten
# This is free software under the GNU General Public License V2

##################################################################################################
# Changelog
###
#  0.1  - first stable version
#  0.2  - command line options added
#       - lock function added
#       - code cleanup
#       - fail gracefully if no pic today
#  0.3  - don't override environment's PATH
#       - setting apple desktop wallpaper
#       - now using apod.nasa.gov
#       - added archive command
#  0.4  - wallpaper: multi screen support on OS X
#  0.5  - python rewrite
#       - cache directory added
version = "0.5a"

##################################################################################################
# imports
###
import sys
import os
import errno
import logging
from optparse import OptionParser
import re
from cStringIO import StringIO
from subprocess import Popen, PIPE

try:
	from BeautifulSoup import BeautifulSoup
	import requests
	from PIL import Image

except:
	print >> sys.stderr, "ERROR: missing python modules. Make sure to install"
	print >> sys.stderr, "       beautifulsoup, requests, and pil"
	sys.exit( 5 )

##################################################################################################
# APOD class
###
class ApodSite( object ):
	"""
	Class to handle HTTP communication with the APOD website.
	Returns data as preprocessed objects. 
	"""

	def __init__( self ):
		"""
		Class constructor. Takes no options. No HTTP data is fetched upon
		construction. The get() method must be called explicitly.
		"""
		self.archive = None
		self.urlbase = 'http://apod.nasa.gov/apod'
		self.url = None
		self.picurl = None
		self.explanation = None
		self.title = None
		self.soup = None

	def get( self, date = None ):
		"""
		Method to initate an HTTP get for the APOD specified by optional date.
		The default date is today's picture.

		The date parameter is saved for later use.
		"""
		self.date = date
		self.url = self.dateToUrl( date )
		request = requests.get( self.url )
		try:
			request = requests.get( self.url )
			request.raise_for_status()

		except requests.exceptions.HTTPError:
			print >> sys.stderr, 'Not found:', request.url
			raise

		else:

			# buffer HTML in a soup object
			self.soup = BeautifulSoup( request.text )
			assert len( self.soup ) >= 2

			# extract title			
			self.title = None
			self.title = self.soup.b.string
			assert self.title

			# extract explanation as soup object
			self.explanation = None
			self.explanation = self.soup('p')[2]
			assert self.explanation

			# extract image link and convert to URI
			img = self.soup('p')[1].find('img')
			if img:
				self.picurl = self.urlbase + "/" + img.parent['href']
			else:
				self.picurl = ""
			
			# parse navigation link list at the end of page
			links = self.soup('p')[4].findAll('a')
			assert len( links ) > 5
			self.next = None
			self.prev = None
			for l in links:
				# link to previous APOD
				if l.text == "&lt;":
					try:
						match = re.search( 'ap([0-9]{6}).html', l['href'] )
						self.prev = match.group(1)
					except:
						self.prev = None

				# link to discussion page contains date in YYMMDD format
				# only parse if no date was given
				if not self.date and l.text == "Discuss":
					self.date = l['href'].split('=')[1]
					self.url = self.dateToUrl( self.date )

				# link to next APOD
				# CAVE: is set even if there is no tomorrow yet
				# TODO: don't parse if today's picture / no date given
				if l.text == "&gt;":
					try:
						match = re.search( 'ap([0-9]{6}).html', l['href'] )
						self.next = match.group(1)
					except:
						self.next = None

	def getNext( self ):
		"""
		Advances to the date specified in the member variable next
		which is automatically filled upon get() if the APOD for that
		date contains the bottom link to next picture. Implicitly
		calls get().
		"""
		if self.next:
			self.get( self.next )
			return True
		else:
			return False

	def getPrev( self ):
		"""
		Advances to the date specified in the member variable prev
		which is automatically filled upon get() if the APOD for that
		date contains the bottom link to previous picture. Implicitly
		calls get().
		"""
		if self.prev:
			self.get( self.prev )
			return True
		else:
			return False

	def getLatestWithPic( self, date ):
		"""
		Perform getPrev() until it hasPic().
		"""
		if not self.url:
			self.get( date )
		while not self.hasPic():
			self.getPrev()

	def dateToUrl( self, date = None ):
		"""
		Converts date string in YYMMDD format to a complete APOD URI.
		"""
		if date:
			return self.urlbase + "/ap" + date + ".html"
		else:
			return self.urlbase

	def hasPic( self ):
		"""
		Returns True if the APOD page fetched by the previous get()
		contains an img link, else None.

		Even if True, there is still a chance that the image link
		returned by picUrl() cannot be converted to a PNG.
		"""
		if self.picurl:
			return True
		else:
			return False

	def picDate( self ):
		"""
		Returns date of APOD page fetched by previous get(). This is
		useful if you call get() without date parameter to fetch today's
		APOD.

		Might still return None if the page could not be parsed for the date.
		"""
		return self.date

	def picUrl( self ):
		"""
		Returns image URI in APOD page fetched by previous get(), else None.
		"""
		return self.picurl

	def picTitle( self ):
		"""
		Returns title of APOD fetched by previous get(),
		else None.
		"""
		return self.title.strip()

	def picExplanation( self ):
		"""
		Returns HTML explanation of APOD fetched by previous get(), else None.

		Currently returns broken text string.
		"""
		text = self.explanation( text = True )
		text = ' '.join( text ).replace( '\n', ' ' )
		text = text.replace( "  ", " " ).replace( "  ", " " ).replace( "  ", " " )
		return text.strip()

	def getPic( self ):
		"""
		Performs HTTP get on image in APOD page fetched by previous get().
		Returns raw image data as string object or None if no URI was set. 
		"""
		if self.picurl:
			return requests.get( self.picurl ).content
		else:
			return None

	def getArchive( self ):
		"""
		Performs HTTP get and returns dictionary of all "date":"title" pairs.
		"""
		if not self.archive:
			request = requests.get( "http://apod.nasa.gov/apod/archivepix.html" )
			soup = BeautifulSoup( request.text )
			self.archive = {}
			for link in soup.b('a'):
					date = link['href'][2:8]
					desc = link.text
					self.archive[date] = desc
		return self.archive

	def info( self ):
		"""
		Returns string containing current status.
		"""
		ret = "date:" + self.date
		ret += "\nurl:" + self.url
		ret += "\nnext:" + self.next
		ret += "\nprev:" + self.prev
		ret += "\npicurl:" + self.picurl
		return ret

	def __str__( self ):
		return self.info()

##################################################################################################
# ApodPic class
###
class ApodPic( object ):

	def __init__( self, data ):
		io = StringIO( data )
		self.im = Image.open( io )
		self.im.convert('RGBA')

	def saveAs( self, name ):
		self.im.save( name )


##################################################################################################
# ApodCace class
###
class ApodCache( object ):

	def __init__( self, path ):
		self.path = path
		if os.path.isfile( path ):
			raise NameError( path + "points to an existing file" )
		else:
			self.mkdir( path )

	def mkdir( self, path ):
		if not os.path.isdir( path ):
			try:
				os.makedirs( path )
			except OSError as e:
				if e.errno == errno.EEXIST:
	 				pass
				else:
					raise

	def dir( self ):
		return os.listdir( self.path )

	def file( self, name ):
		return self.path + "/" + name

	def cacheName( self, name ):
		if self.path in name:
			return name[len( self.path ):]
		else:
			return name

	def isCached( self, name ):
		cachename = aelf.cacheName( name )
		return cachename in self.dir()

	def mtime( self, name ):
		return os.path.getmtime( self.file( name ) )

	def pics( self ):
		pics = []
		allfiles = sorted( self.dir() )
		for name in allfiles:
			if name[0:5] == "apod-":
				mtime = self.mtime( name )
				pics.append( {'name':name, 'mtime':mtime} )
		sortedpics = sorted( pics, key = lambda pic: pic['mtime'], reverse = True )
		return [ pic['name'] for pic in sortedpics ]

	def files( self ):
		return [ self.file( pic ) for pic in self.pics() ]

	def cleanup( self, cachemax ):
		pics = self.pics()
		cachefill = len( pics )
		cachemax = int( cachemax )
		if cachefill > cachemax:
			for name in pics[cachemax-cachefill:]:
				self.delete( name )

	def delete( self, name ):
		os.unlink( self.path + "/" + name )

##################################################################################################
# Wallpaper class
###
class Wallpaper( object ):
	"""
	Class abstracting OS-specific wallpaper operations
	"""
	def __init__( self ):
		self.ostype = "unknown"
		self.available = False
		self.set = None

		if os.sys.platform == 'darwin':
			if os.path.isfile( '/usr/bin/osascript' ):
				self.available = True
				self.ostype = "Darwin"
				self.set = self.setDarwin

	def setDarwin( self, filenames ):
		nr = 0
		for f in filenames:
			nr += 1
			if os.path.isfile( f ):
				script = '''
					set picFile to POSIX file "''' + f + '''"
					set nr to ''' + str( nr ) + '''
					tell application "System Events"
						set picture of desktop nr to picFile
					end tell
				'''
				arg = []
				p = Popen( ['/usr/bin/osascript', '-'] + arg,
					stdin = PIPE, stdout = PIPE, stderr = PIPE )
				stdout, stderr = p.communicate( script )
				# CAVE: discard all osascript errors
				#print p.returncode, stdout, stderr


##################################################################################################
# main
###
opt = {}
args = []
def main():
	usage = "usage: %prog [options] command [arguments ...]"
	parser = OptionParser( usage=usage, version="%prog "+version )
	parser.add_option( "-d", "--date", dest="date", metavar="DATE",
        help="specify date for APOD as YYMMDD (default most recent)" )
	parser.add_option( "-s", "--screens", dest="screens", metavar="NR",
        help="Number of screens for wallpaper actions (default 1)" )
	parser.add_option( "-b", "--backlog", dest="backlog", default=5,
        help="number of pictures retained in cache (default 5)" )
	parser.add_option( "-c", "--cache", dest="cache", default=os.getenv("HOME")+"/.apod",
        help="directory for picture cache (default $HOME/.apod)" )
	parser.add_option( "-v", "--verbose", action="store_true", dest="verbose", default=False,
        help="show what's going on (default: false)" )
	(opt, args) = parser.parse_args()

	# command is mandatory ############################################
	if len( args ) == 0:
	    print >> sys.stderr, "ERROR: you must specify a command"
	    sys.exit( 6 )
	command = args[0]

	# save command ####################################################
	if command == "save":
		apod = ApodSite()
		apod.get( opt.date )
		if apod.hasPic():
			print "Fetching", apod.picUrl()
			pic = ApodPic( apod.getPic() )

			if len( args ) > 1:
				name = args[1]
			else:
				name = "apod-" + apod.picDate() + ".png"
			print "Saving", name
			pic.saveAs( name )
		else:
			print "No picture for", apod.picDate()

	# info command ####################################################
	elif command == "info":
		apod = ApodSite()
		apod.get( opt.date )
		print apod

	# explain command #################################################
	elif command == "explain":
		apod = ApodSite()
		apod.get( opt.date )
		print apod.picDate(), apod.picTitle()
		print
		print apod.picExplanation()

	# archive command #################################################
	elif command == "archive":
		apod = ApodSite()
		archive = apod.getArchive()
		for date, desc in sorted( archive.items() ):
			print date, desc

	# cache command ###################################################
	elif command == "cache":
		cache = ApodCache( opt.cache )
		print cache.files()

	# wallpaper command ###############################################
	elif command == "wallpaper":
		if len( args ) > 1:
			filenames = args[1:]
		else:
			cache = ApodCache( opt.cache )
			filenames = cache.files()
		wp = Wallpaper()
		if wp.available:
			print "Setting desktop wallpaper(s) to", filenames
			wp.set( filenames )
		else:
			print >> sys.stderror, "ERROR: unsupported os type " + wp.ostype

	# update command ##################################################
	elif command == "update":
		cache = ApodCache( opt.cache )
		apod = ApodSite()
		apod.getLatestWithPic( opt.date )
		name = cache.path + "/apod-" + apod.picDate() + ".png"
		if not os.path.isfile( name ):
			pic = ApodPic( apod.getPic() )
			pic.saveAs( name )
		cache.cleanup( opt.backlog )
		wp = Wallpaper()
		if wp.available:
			wp.set( cache.files() )

	# command error ###################################################
	else:
		print >> sys.stderr, "ERROR: invalid command:", command
		sys.exit( 4 )

if __name__ == "__main__":
    main()
