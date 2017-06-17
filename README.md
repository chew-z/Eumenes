# Eumenes

Script for adding Spotify playlists to Apple Music....


## Quick start

Try something like:

```
python3 eumenes.py -s US -c JP --auto -p spotify:user:121157076:playlist:58vO2KZUGQnB0OUmhiiBKA
```

You can get fine playlists from [playlist.net](http://playlists.net/) *Hint - right click green Play button and select Copy Link Address*

## How it works

1) Process Spotify playlist and save necessary info as csv
2) Search iTunes, find and select best match
3) Add selected track to Apple Music (iTunes). Repeat 2)
4) Create XML for importing playlist into iTunes Library

Inspired by [spotify2am](https://github.com/simonschellaert/spotify2am).

Depends on methods in anabasis.py.

Requires you to intercept iTunes cookie as [best described here](https://apple.stackexchange.com/questions/193731/sync-transfer-spotify-playlist-to-apple-music/194528).
*Personally I am using [mitmproxy](https://github.com/mitmproxy/mitmproxy) for this - better and free - instead of Charles Proxy.*

After intercepting iTunes traffic you have to edit **headers.conf** and change **X-Dsid**, **X-Guid** and **Cookie**. 
IT WON"T WORK OTHERWISE.

## What's cool about it?

* Uses matching algorithm of my own design based on lexical proximity (of title, artist, album) and time proximity of release dates
* Selecting matching tracks is either automatic or user chooses best match manually from candidates
* Matching conditions are flexible - good matches pass automatically, dubious matches are left to user decision
* You can search and add tracks in any country (technically iTunes storefront)
* Flexible delay mechanism dealing with 403 error (Too many requests) when searching iTunes and adding tracks
* Builds XML playlist for importing into iTunes 
* Honors Spotify playlist title and comments
* Everything in one script - retrieving Spotify info, matching with Apple Music, adding tracks, building playlist XML
* Pretty detailed logging - educational if you fancy looking into logs

## Usage

```
usage: eumenes.py [-h] [-p PLAYLIST] [-q] [-s SEARCH_STORE] [-c COUNTRY_STORE]
                  [--csv] [--xml] [--am] [-e ERROR] [-a] [-t TRESHOLD]
                  [-d DELAY]

Tool for adding Spotify playlists to Apple Music. 1) Process Spotify playlist
and save necessary info as csv 2) Search iTunes, find and select best match 3)
Add selected track to Apple Music (iTunes) 4) Create XML for importing
playlist to iTunes Library

optional arguments:
  -h, --help            show this help message and exit
  -p PLAYLIST, --playlist PLAYLIST
                        Spotify playlist to start with [Spotify id] (default:
                        spotify:user:115856134:playlist:1y6UWnWIRvAArSaUY1Gy25
                        )
  -q, --quiet           Cut down noise in screen output and logging (default:
                        False)
  -s SEARCH_STORE, --search_store SEARCH_STORE
                        iTunes store front [country] used for searching
                        (default: US)
  -c COUNTRY_STORE, --country_store COUNTRY_STORE
                        iTunes store front [country] used for adding tracks
                        (default: JP)
  --csv                 If False don't save Spotify playlist as csv. You need
                        this csv so it only makes sense if you process same
                        playlist for a second time. (default: True)
  --xml                 If False don't create XML with iTunes playlist
                        (default: True)
  --am                  If False skip adding tracks to iTunes (default: True)
  -e ERROR, --error ERROR
                        Error margin. Time-lexical distance between tracks to
                        be considered insignificant. This should be rather
                        small because even if --auto option (see --auto) is
                        False very close tracks will be still selected without
                        asking user. (default: 0.11)
  -a, --auto            If True accept best matching tracks without user
                        intervention even if they at certain time-lexical
                        distance (see --threshold). Time-lexical = similar
                        title, artist, album and close release dates.
                        (default: False)
  -t TRESHOLD, --treshold TRESHOLD
                        Maximum distance for best match to be accepted
                        automatically without asking user [0.0 - 1.0]. High
                        value will let pass many false positives however you
                        may need higher values if searching iTunes generates
                        results that are consistently far from Spotify tracks.
                        It deepend a lot on storefront (country) used for
                        searching tracks. For example in Japanese store artist
                        name and album tittle even for Western albums could be
                        often in Japanese script and obviously they poorly
                        match to Spotify tracks in English. 'Deluxe Edition',
                        'Remastered', 'Remix', 'featuring' - titles ain't
                        identical. Sometimes it is local name, different
                        romanization etc. Experiment. Read logs. Optimal
                        treshold may differ between playlists and music
                        genres. (default: 0.4)
  -d DELAY, --delay DELAY
                        Delay in seconds between requests to iTunes to avoid
                        403 error - Too many requests. Longer delays make
                        execution painful but with large playlist you might
                        need 30 seconds delay. (default: 30)
```

## Some remarks

* It takes time even for medium length playlists. There is a delay after adding each track to Apple Music to avoid being banned due to too many requests.
* Give iTunes time - iTunes work asynchronously based on queues, it takes time to update local Library and process new additions.
* Wait a little before importing playlist from XML, import works better if tracks have been already processed and downloaded by iTunes
* In a playlist set view to *Songs* and add column with iCloud status. It helps to see what is going on.
* If a playlist is marked with crossed cloud be patient, iTunes will mark it as OK once it processes all tracks.
* If you get into trouble with tracks *No Longer Available*, *Error* try again. Run eumenes.py again on the same playlist. Remove playlist and add again. Etc.
* Some pretty obvious tracks cannot be found (it is mostly technicality as they are not marked as *isStreamable*) I am working on it.
* Watch in logs for error 403 - Too many requests.


I have tested only under python 3

There could be still some errors handling various edge cases (like no connection, proxy, some weird chars etc.) resulting in crashes. Please let me know on Issues.

## Anabasis

This is library with methods used by eumenes.py (and some my other scripts).

## Using VIM?

Try my [itunes.vim plugin](https://github.com/chew-z/itunes.vim).

## Eumenes, Anabasis?

Got tired of finding functional names for my scripts.

### Eumenes

*Eumenes of Cardia - Greek scribe at Alexander's The Great court who after Alexander's death remained loyal defender of royal house and proved himself excellent general beating in battle and killing (in hand to hand combat) some of most distinguished Macedonian marshals.*

[Eumenes - wikipedia](https://en.wikipedia.org/wiki/Eumenes)

[Ghost On the Throne](http://www.goodreads.com/book/show/10767816-ghost-on-the-throne#)

### Anabasis

*Xenophon's March of Ten Thousand - history of Greek mercenaries epic march to extricate themselves from Persia after defeat. Called one of the great adventures in human history.*

[Anabasis by Xenophon](http://www.gutenberg.org/ebooks/1170?msg=welcome_stranger)

