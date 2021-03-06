#!/bin/bash
# apod - download the Astronomy Picture of the day
# (c) 2003-20012 Christiane Ruetten
# This is free software under the GNU General Public License V2

# Changelog:
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
version='0.4'

#############################################################################
# how to use this program
#####

usage () {
	cat <<-EOF
	apod $version
	Download the Astronomy Picture of the Day
	(c) 2003-2012 Christiane Ruetten
	Free software licensed under GPLv2
	
	usage:  $(basename "$0") update|get|lock|unlock|wallpaper|archive [<options> ...]
	
	commands:
	        update [<file> [<date>]]
	             loads image to file, ~/apod.png if unspecified. Format of
	             optional date is YYMMDD. If unspecified, today's picture
	             is loaded.
	
	        get [<file> [<date>]]
	             Same as update, but ignores the locking.
	
	        lock
	             prevents subsequent updates from running. Useful if you
	             have the script running as a cronjob but like today's
	             picture so much.
	
	        unlock
	             removes the locking flag.

	        wallpaper [<file>]
	             set wallpaper on desktop.

	        archive [<searchterm>]
	             list APOD archive, optionally filter titles.	

	automatic updates:
	        Run the shell command "crontab -e" and add a line like:

	        @hourly /home/cr/apod.sh update /home/cr/Images/apod.png \\
	             && /home/cr/apod.sh wallpaper /home/cr/Images/apod.png

	        You may also use @daily or @reboot if your system is permanently
	        online.
	
	EOF
}


#############################################################################
# general environment variables
#####

# base URL of APOD site
URLBASE='http://apod.nasa.gov/apod'
#
MARKER='href="image/'
# path not set in all environments (eg. some cron)
PATH=/bin:/usr/bin:/sbin:/usr/sbin:/usr/local/bin:/opt/local/bin:$PATH
#PROXY='http://user:password@wwwproxy.domain.de:8080'


#############################################################################
# the APOD functionality
#####

get_apod () {
	local picfile=${1:-$HOME/apod.png}
	local date=$2
	local picext=${picfile##*.}
	local page=${date:+ap$date.html}

	export http_proxy=$PROXY
	# extract path to APOD from webpage
	picname=$(
		wget "$URLBASE/$page" -t 10 -w 300 -q -O - \
		  | grep $MARKER \
		  | tr '"' '\n' \
		  | head -n2 \
		  | tail -n1
	)

	[ -z "$picname" ] && echo "No astronomy picture today." >&2 && exit 1

	# and load it to tmpfile
	wget "$URLBASE/$picname" -t 10 -w 300 -q -O "$tmp"

	# try conversion, keep backup
	# TODO: handle gracefully if directory
	if $convert "$tmp" "$tmp.$picext" 
	then
		[ -e "$picfile" ] && cp -pf "$picfile" "$picfile~"
		mv "$tmp.$picext" "$picfile"
	fi

}

set_apple_wallpaper () {
	image=$1
	osascript <<- EOF
	set picFile to POSIX file "$image"
	tell application "Finder"
	set desktop picture to picFile
	end tell
	tell application "System Events"
	set picture of every desktop to picFile
	set picture of desktop 1 to picFile
	set picture of desktop 2 to picFile
	set picture of desktop 3 to picFile
	end tell
	EOF
}

set_wallpaper() {
    imagefile=$1
    if which osascript &>/dev/null
    then
		#Set OS X wallpaper
		#force-change to updated picture by changing to a new name first
		tmpfile="/tmp/apod_${imagefile##*/}"
		cp "$imagefile" "$tmpfile"
		set_apple_wallpaper "$tmpfile"
		set_apple_wallpaper "$imagefile"
		rm -f "$tmpfile"
	else
		echo "Currently only OS X is supported. Please set wallpaper manually."
    fi
	
}

list_archive() {
    wget "$URLBASE/archivepix.html" -q -O - \
      | grep ".*[12][90].*:  <a href" \
      | while read y m d a line
      do
		line=${line#href=\"}
		image=${line%%\"*}
		line=${line#*\">}
		title=${line%</a>*}
        date=${image%.html}
		date=${date#ap}
		url="$URLBASE/ap$date.html"
	    echo "$date	$url	$title"
      done
}

sanity_check () {

	if ! which wget >&/dev/null
	then
		echo "ERROR: wget required. Please install." >&2
		exit 1
	fi

	convert=$(which gm 2>/dev/null)
	[ -n "$convert" ] && convert="$convert convert"
	[ -z "$convert" ] && convert=$(which convert 2>/dev/null)

	if [ -z "$convert" ]
	then
		echo "ERROR: either ImageMagick or GraphicsMagick required. Please install."
		exit 1
	fi

	ping -c1 www.nasa.gov &>/dev/null || exit 1

}

tmp="/tmp/apod_$RANDOM$RANDOM"
cleanup () {
	rm -rf "$tmp"* >&/dev/null
}
trap cleanup 0 1 15


#############################################################################
# main script logic
#####

# can we run?
sanity_check

# yes we can

cmd=$1
case "$cmd" in

  update)
	picfile=${2:-$HOME/apod.png}
	date="$3"
	if [ -e "$HOME/.apod_noupdate" ]
	then
		echo "WARNING: Not updating. Current picture is locked." >&2
	else
		get_apod "$picfile" "$date"
		date >"$HOME/.apod_run"
	fi
	;;

  get|set)
	picfile=${2:-$HOME/apod.png}
	date="$3"
	get_apod "$picfile" "$date"
	date >"$HOME/.apod_run"
	;;

  lock|keep|noupdate)
	touch "$HOME/.apod_noupdate"
	;;

  unlock|cont*)
	rm -f "$HOME/.apod_noupdate" 2>/dev/null
	;;

  wallpaper)
	picfile=${2:-$HOME/apod.png}
	set_wallpaper "$picfile"
	;;

  archive)
	search=$2
	if [ -n "$search" ]
	then
		list_archive | egrep -i "$search"
	else
		list_archive
	fi
	;;

  *help)
	usage
	;;

  *)
	if [ -n "$cmd" ]
	then
		echo "ERROR: unknown command: $cmd" >&2
	fi
	usage
	exit 1

	;;

esac

