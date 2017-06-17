#!/usr/bin/env python
'''
Tool for adding Spotify playlists to Apple Music.
1) Process Spotify playlist and save necessary info as csv
2) Search iTunes, find and select best match
3) Add selected track to Apple Music (iTunes)
4) Create XML for importing playlist to iTunes Library

Named after Eumenes of Cardia - Greek scribe at Alexander's The Great court
who after Alexander's death remained loyal defender of royal house and proved
himself excellent general beating in battle and killing (in hand to hand combat)
some of most distingushed Macedonian marshals.
https://en.wikipedia.org/wiki/Eumenes
http://www.goodreads.com/book/show/10767816-ghost-on-the-throne#
'''
import anabasis
import argparse
import arrow
import csv
import datetime
import logging
import os
import plistlib
import requests
import spotipy
import spotipy.oauth2 as oauth2
import sys
from lxml import etree
from slugify import slugify
from time import sleep


def distance(am_track, spf_track):
    '''
    wrapper for calling anabasis.get_tracks_distance()
    distance is used as key for sorting candidates
    '''
    a_track = am_track['trackName']
    a_artist = am_track['artistName']
    a_album = am_track['collectionName']
    a_year = am_track['releaseDate']
    b_track = spf_track['title']
    b_artist = spf_track['artist']
    b_album = spf_track['album']
    b_year = spf_track['release_date']
    dist = anabasis.get_tracks_distance(
        a_track,
        a_artist,
        a_album,
        a_year,
        b_track,
        b_artist,
        b_album,
        b_year)
    return dist


def addTrack(_id, _c):
    '''
    Wrapper for anabasis.add_track_AM()
    Here we can handle various errors and edge cases
    Returns True if we might hope that track has been successfuly added
    False otherwise.
    '''
    try:
        resp = anabasis.add_track_AM(_id, _country=_c)
        if resp == requests.codes.ok:
            logging.info(
                "Track {} added to Apple Music".format(_id))
            return True
        elif resp == requests.codes.forbidden:
            logging.info(
                "Got 403 (Forbidden - Too many requests) for a first time. Re-trying...")
            # # wait and re-try once
        elif resp == requests.codes.not_found:
            logging.info(
                "Got 404 (Not Found) for track {}..".format(_id))
            # print("Track {} seems unavailable in {} store.".format(_id, c_store))
        elif resp == requests.codes.bad_request:
            logging.info(
                "Got 400 (Bad Request) for track {}. Using wrong storefront {}? ".format(_id, c_store))
            print('''Got error 400 (Bad request) adding track to Apple Music. Have you choosen right storefront {} for
            your account ?'''.format(c_store))
        else:
            logging.error(resp)
    except Exception as e:
        logging.error(e)
        pass

    return False


def dump_csv(songs, fpath):
    '''
    save Spotify playlist as csv including track id, track url, release date
    '''
    if verbose:
        print('Saving Spotify playlist as csv file')
    with open(fpath, 'w') as l:
        # header row
        line = "spotify_id;track_url;title;artist;album;album_url;release_date\n"
        l.write(line)
        for item in songs['items']:
            tr = item['track']
            al = sp.album(tr['album']['id'])
            if verbose:
                # progress dot (this could be lenghty process)
                print('.', end='', flush=True)
            line = "{};{};{};{};{};{};{}\n".format(
                tr['id'],
                tr['external_urls']['spotify'],
                tr['name'].replace(';', ':'),
                tr['artists'][0]['name'].replace(';', ':'),
                tr['album']['name'].replace(';', ':'),
                tr['album']['external_urls']['spotify'],
                al['release_date'])
            l.write(line)
    if verbose:
        print("\nSaved to {}".format(fpath))


def add_tracks_from_CSV(fpath, c_store='JP', s_store='US', _add_tracks=True, _err=0.11, _auto=True, _treshold=0.4,
        _delay=5):
    '''
    match Spotify tracks with iTunes/Apple Music tracks and add selected tracks
    to Apple Music - based on Spotify playlist info stored in csv file
    '''
    am_playlist = []
    with open(fpath) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            song = {'title': row['title'],
                    'artist': row['artist'],
                    'album': row['album'],
                    'release_date': row['release_date']}

            logging.info(
                "Searching for track {}, {}, {}, {}".format(
                    song['title'],
                    song['artist'],
                    song['album'],
                    song['release_date']))
            # candidates (search results) and their usefullness
            # deepends a lot on selected storefront (country and locale).
            candidates = anabasis.searchSongs(
                song['title'],
                song['artist'],
                song['album'],
                _country=s_store)

            if len(candidates) == 0:
                print(
                    "Couldn't find {} - {} in Apple Music {}!".format(song["title"], song['artist'], s_store))
                continue
            elif len(candidates) == 1:
                # TODO - single result doesn't imply good result.
                selected = candidates[0]
            else:
                # first sort candidates according to distance from Spotify track
                # search results are quite well sorted courtesy of Apple but
                candidates = sorted(
                    candidates, key=lambda x: distance(x, song))
                for c in candidates:
                    logging.info("{:6.4f} - {}| {}| {}".format(
                        distance(c, song),
                        c['trackName'],
                        c['collectionName'],
                        c['artistName']))
                # if best match is within rounding error
                dist = distance(candidates[0], song)
                if dist < _err:
                    selected = candidates[0]
                    logging.info('''Track {} - {} selected automatically becaues distance {:4.2f} is within {:4.2f} rounding
                            error'''.format(selected['trackId'], selected['trackName'], dist, _err))
                # auto-accept best match within treshold distance
                elif _auto and (dist < _treshold):
                    selected = candidates[0]
                    logging.info('''Track {} - {} selected automatically becaues option _auto is {} and distance {:4.2f}
                    is within {:4.2f}'''.format(selected['trackId'], selected['trackName'], _auto, dist, _treshold))
                # or else let user select or pass
                else:
                    selected = anabasis.selectSong(candidates, song)
                    if selected is None:
                        logging.info('User skiped this track!')
                        continue
                    else:
                        logging.info("User manually selected track {} - {}".format(selected['trackId'],
                            selected['trackName']))
            if verbose and selected is not None:
                # logging.info(selected)
                logging.info("Selected track {} - {}, {}, {}".format(selected['trackId'],
                    selected['trackName'],
                    selected['artistName'], 
                    selected['collectionName']))
                print(
                    "Selected: {} - {}".format(selected['trackName'], selected['artistName']))

            itunes_id = selected['trackId']
            if _add_tracks:
                if addTrack(itunes_id, c_store):
                    am_playlist.append(selected)
                    sleep(_delay)
            else:
                am_playlist.append(selected)

    return am_playlist


def buildXML(playlist, _title="Playlist", _description=""):
    '''
    build Apple Music playlist as xml for importing into iTunes
    '''
    _tracks = {}
    _track_id = 10000
    if verbose:
        print('Saving playlist as XML')
    for song in playlist:
        _tracks[str(_track_id)] = {
            # TODO - which Track ID works best?
            "Track ID": _track_id,
            # "Track ID": song['trackId'],
            "Apple Music": True,
            "Artist": song['artistName'],
            "Album": song['collectionCensoredName'],
            "Bit Rate": 256,
            # "Comments": "{}".format(tr['external_urls']['spotify']),
            "Disc Count": song['discCount'],
            "Disc Number": song['discNumber'],
            "Genre": song['primaryGenreName'],
            "Kind": "Apple Music AAC audio file",
            "Name": song['trackName'],
            "Play Count": 0,
            "Playlist Only": True,
            "Sample Rate": 44100,
            "Sort Album": song['collectionName'],
            "Sort Artist": song['artistName'],
            "Sort Name": song['trackName'],
            "Time": 255,
            "Total Time": song['trackTimeMillis'],
            "Track Number": song['trackNumber'],
            "Track Count": song['trackCount'],
            "Track Type": "Remote",
            "Year": arrow.get(song['releaseDate']).year
        }
        _track_id += 2
        if verbose:
            print('.', end='', flush=True)   # progress dot

    playlistItems = [{"Track ID": _track["Track ID"]}
                     for (_, _track) in _tracks.items()]

    pl = {
        "Application Version": "12.6.1.25",
        "Date": datetime.datetime.now(),
        "Features": "5",
        "Major Version": "1",
        "Minor Version": "1",
        "Show Content Ratings": True,
        "Tracks": _tracks,
        "Playlists": [{
            "All Items": True,
            "Description": _description,
            "Name": _title,
            "Playlist ID": 100001,
            "Playlist Items": playlistItems,
        }],
    }
    plistStr = plistlib.dumps(pl)

    # Here comes the tricky and dirty part: we need to manipulate the xml nodes
    # order manually to make the "Playlist" come after "Tracks".
    plist = etree.fromstring(plistStr)
    parent = plist.getchildren()[0]
    children = plist.getchildren()[0].getchildren()

    for i in range(len(children)):
        if children[i].text == "Playlists":
            playlistKey = children[i]
            playlistArr = children[i + 1]
            parent.remove(playlistKey)
            parent.remove(playlistArr)
            parent.append(playlistKey)
            parent.append(playlistArr)
            break

    return etree.tostring(
        plist, pretty_print=True, encoding="UTF-8", xml_declaration=True,
        doctype='<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" \
        "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
    ).decode("utf-8")


def getArgs(argv=None):
    parser = argparse.ArgumentParser(description='''Tool for adding Spotify playlists to Apple Music.
                        1) Process Spotify playlist and save necessary info as csv
                        2) Search iTunes, find and select best match
                        3) Add selected track to Apple Music (iTunes)
                        4) Create XML for importing playlist to iTunes Library''',
                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-p', '--playlist',
                        default='spotify:user:115856134:playlist:1y6UWnWIRvAArSaUY1Gy25',
                        help='Spotify playlist to start with [Spotify id]')
    parser.add_argument('-q', '--quiet', default=False,
                        action="store_true",
                        help='Cut down noise in screen output and logging')
    parser.add_argument('-s', '--search_store', default='US',
                        help='iTunes store front [country] used for searching')
    parser.add_argument('-c', '--country_store', default='JP',
                        help='iTunes store front [country] used for adding tracks')
    parser.add_argument('--csv', default=True,
                        action="store_false",
                        help='''If False don\'t save Spotify playlist as csv. You need this csv so it only makes sense
                        if you process same playlist for a second time.''')
    parser.add_argument('--xml', default=True,
                        action="store_false",
                        help='If False don\'t create XML with iTunes playlist')
    parser.add_argument('--am', default=True,
                        action="store_false",
                        help='If False skip adding tracks to iTunes')
    parser.add_argument('-e', '--error', default=0.11,
                        help='''Error margin. Time-lexical distance between tracks to be considered insignificant.
                        This should be rather small because even if --auto option (see --auto) is False very close
                        tracks will be still selected without asking user.''')
    parser.add_argument('-a', '--auto', default=False,
                        action="store_true",
                        help='''If True accept best matching tracks without user intervention even if they at certain
                        time-lexical distance (see --threshold). Time-lexical = similar title, artist, album and
                        close release dates.''')
    parser.add_argument('-t', '--treshold', default=0.40,
                        help='''Maximum distance for best match to be accepted automatically without asking user 
                        [0.0 - 1.0].
                        High value will let pass many false positives however you may need higher values if searching
                        iTunes generates results that are consistently far from Spotify tracks. 
                        It deepend a lot on storefront (country) used for searching tracks. For example in Japanese 
                        store artist name and album tittle even for Western albums could be often in Japanese script 
                        and obviously they poorly match to Spotify tracks in English.
                        \'Deluxe Edition\', \'Remastered\', \'Remix\', \'featuring\' - titles ain't identical.
                        Sometimes it is local name, different romanization etc.
                        Experiment. Read logs.
                        Optimal treshold may differ between playlists and music genres.''')
    parser.add_argument('-d', '--delay', default=30,
                        help='''Delay in seconds between requests to iTunes to avoid 403 error - Too many requests.
                        Longer delays make execution painful but with large playlist you might need 30 seconds delay.''')
    return parser.parse_args(argv)


def process(_csv=True, _am=True, _xml=True, _e=0.11, _a=True, _t=0.4, _d=5):
    # spotify_uri =
    # 'spotify:user:spotifycharts:playlist:37i9dQZEVXbJiZcmkrIHGU'
    username = spotify_uri.split(':')[2]
    playlist_id = spotify_uri.split(':')[4]

    playlist = sp.user_playlist(username, playlist_id)
    tracks = playlist['tracks']
    # logging.info(json.dumps(playlist, indent=4))

    pl_name = slugify(playlist['name'], ok='-_()[]{}', lower=False)
    if playlist['description']:
        pl_desc = playlist['description']
    else:
        pl_desc = ""

    logging.info("{} - {}".format(playlist['name'], playlist['description']))
    if verbose:
        print("--- eumenes.py starting... ---")
        print("Processing Spotify playlist '{}' : '{}'".format(
            playlist['name'], playlist['description']))

    pl_path = "Spotify-playlists/{}.csv".format(pl_name)
    if _csv:
        dump_csv(tracks, pl_path)
    # TODO - check explicite if csv exists
    if not os.path.isfile(pl_path):
        print("Cannot find {}".format(pl_path))
        sys.exit(1)
    am_pl = add_tracks_from_CSV(
        pl_path,
        c_store=country_store,
        s_store=search_store,
        _add_tracks=_am,
        _err=_e,
        _auto=_a,
        _treshold=_t)
    if _xml:
        xml_pl = buildXML(am_pl, _title=playlist['name'], _description=pl_desc)
    logging.info(xml_pl)
    xml_path = "AM-playlists/{}.xml".format(pl_name)
    print('\n---')
    with open(xml_path, "w") as xmlf:
        xmlf.write(xml_pl)
    print(
        "Done.\nYou can import your playlist [iTunes Menu: File-Library-Import Playlist] from {}".format(
            xml_path))


if __name__ == '__main__':
    FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
    try:
        os.remove('eumenes.log')
    except BaseException:
        pass
    logging.basicConfig(filename='eumenes.log', level=logging.DEBUG,
                        format=FORMAT, datefmt='%a, %d %b %Y %H:%M:%S',)
    logging.info('--- eumenes.py logging started ---.')

    args = getArgs()
    verbose = not args.quiet
    anabasis.verbose = not args.quiet
    anabasis.delay = args.delay
    anabasis.country = args.country_store
    country_store = args.country_store
    search_store = args.search_store

    spotify_uri = args.playlist
    oa2 = oauth2.SpotifyClientCredentials(
        client_id='768998a7e3444c6a82f0c11ddd59c946',
        client_secret='4b1e7672e14a42269ee4a22e11214fdf')
    token = oa2.get_access_token()
    sp = spotipy.Spotify(auth=token)

    process(_csv=args.csv, _am=args.am, _xml=args.xml,
            _e=args.error, _a=args.auto, _t=args.treshold, _d=args.delay)

    logging.info('--- eumenes.py logging finished ---.')
