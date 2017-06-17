#!/usr/bin/env python
'''
Collection of methods for working with Spotify and Apple Music.
Named after Xenophon's March of Ten Thousand
- history of Greek mercenaries epic march to extricate themselves
from Persia after defeat.
Called one of the great adventures in human history.
https://en.wikipedia.org/wiki/Anabasis_(Xenophon)
'''

import os
import shutil
import time
import datetime
import arrow
import struct
import argparse
import logging
import requests
import json
import csv
import spotipy
import difflib
import math
import spotipy.oauth2 as oauth2
import plistlib
from time import sleep
from urllib.parse import urlencode
from lxml import etree
from slugify import slugify


global verbose
global anabasis
global delay


# This could be also ld-4.itunes.apple.com or other. Check for yourself.
addAM_uri = 'https://ld-6.itunes.apple.com/WebObjects/MZDaap.woa/daap/databases/1/cloud-add'
hex = "61 6a 43 41 00 00 00 45 6d 73 74 63 00 00 00 04 55 94 17 a3 6d 6c 69 64 00 00 00 04 00 00 00 00 6d 75 73 72 00 00 00 04 00 00 00 81 6d 69 6b 64 00 00 00 01 02 6d 69 64 61 00 00 00 10 61 65 41 69 00 00 00 08 00 00 00 00 11 8c d9 2c 00"


class DictQuery(dict):
    '''
    Handling key error like a boss
    https://www.haykranen.nl/2016/02/13/handling-complex-nested-dicts-in-python/
    '''

    def get(self, path, default=None):
        keys = path.split("/")
        val = None

        for key in keys:
            if val:
                if isinstance(val, list):
                    val = [v.get(key, default) if v else None for v in val]
                else:
                    val = val.get(key, default)
            else:
                val = dict.get(self, key, default)
            if not val:
                break
        return val


def _storefront(c):
    '''
    https://gist.github.com/loretoparisi/ffb953665885db7dc0ea
    READ.THIS
    We can search any storefront (Bulgarian anyone?) but track names, albums
    and artists - deepends on a country - are likely to have weird names or be
    written in local script which spoils automatics matching tracks with Spotify
    (which provides mostly English-based names).
    However you can get error (400) when adding tracks through storefront other
    then your Apple ID is connected to.
    On the other hand if you search US iTunes you are likely to find results
    not available in other locales.
    Searching "Adele - Hello" results in 36 tracks in US iTunes (mostly crap -
    tributes, remixes, piano versions etc.) and 5 in Japan or Singapore.
    Search US, add through local or search local and choose results manually
    '''
    with open('itunes_storefrontid_list.json') as jsonf:
        store_fronts = json.load(jsonf)
    _s = store_fronts[c]['itunes_storefront_id']
    logging.info("storefront {} = {}".format(c, _s))
    return _s


def _headers(country='US'):

    _h = {}
    with open('headers.conf', 'r') as conf:
        _h = eval(conf.read())

    _h["X-Apple-Store-Front"] = "{},32".format(_storefront(country))

    return _h


def ro_distance(a, b):
    # Ratcliff-Obershelp algorithm
    return 1.0 - \
        difflib.SequenceMatcher(
            lambda x: x in ".()",
            a.upper(),
            b.upper()).ratio()


def aceh_distance(a, b):
    # time distance - closer -> smaller values; infinity -> asymptotic to 1.0
    ad = arrow.get(a)
    bd = arrow.get(b)
    delta = math.fabs((ad - bd).days) / 365
    f = math.log(1 + delta) / (1 + math.log(1 + delta))
    return f


def get_tracks_distance(a_track, a_artist, a_album, a_year,
                        b_track, b_artist, b_album, b_year):
    '''
    Computes time-lexical distance between two tracks based on
    track title, artist, album name, and release date
    '''
    d_track = pow(ro_distance(a_track, b_track), 2)
    d_artist = pow(ro_distance(a_artist, b_artist), 2)
    d_album = pow(ro_distance(a_album, b_album), 2)
    d_years = pow(aceh_distance(a_year, b_year), 2)
    # something else then euclidean metric ? TODO
    d_ = math.sqrt(math.fsum([d_track, d_artist, d_album, d_years])) / 2.0
    if verbose:
        logging.info(
            "{:6.4f}, {:6.4f}, {:6.4f}, {:6.4f} == {:6.4f}".format(
                d_track, d_artist, d_album, d_years, d_))

    return d_


def construct_request_body(timestamp, itunes_identifier):

    body = bytearray.fromhex(hex)
    body[16:20] = struct.pack('>I', timestamp)
    body[-5:] = struct.pack('>I', itunes_identifier)
    return body


def save_sample(path, url):
    '''
    Download sample track from iTunes
    '''
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(path, 'wb') as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)


def add_track_AM(trackId, _country='US'):
    '''
    adds single track to iTunes by ID
    '''
    logging.info("Adding track id {}".format(trackId))
    data = construct_request_body(int(time.time()), trackId)
    try:
        response = requests.get(
            addAM_uri,
            data=data,
            headers=_headers(_country),
            timeout=60)
        logging.info(response.headers)
    except Exception as e:
        logging.error(e)

    return response.status_code


def get_best_match(a_track, a_artist, a_album, a_year, tracks):
    '''
    returns best matching track from iTunes
    '''
    best_match = None
    nearest = 1.0
    for tr in tracks:
        b_track = tr['trackName']
        b_artist = tr['artistName']
        b_album = tr['collectionName']
        b_year = str(tr['releaseDate'])
        if verbose:
            logging.info("{} - {}".format(a_track, b_track))
            logging.info("{} - {}".format(a_artist, b_artist))
            logging.info("{} - {}".format(a_album, b_album))
            logging.info("{} - {}".format(a_year, b_year))
        distance = get_tracks_distance(
            a_track,
            a_artist,
            a_album,
            a_year,
            b_track,
            b_artist,
            b_album,
            b_year)

        if verbose:
            logging.info("{:6.4f} vs {:6.4f}".format(distance, nearest))
        if distance < nearest:
            nearest = distance
            best_match = tr
            if verbose:
                logging.info("Selected {:6.4f}".format(nearest))

    return nearest, best_match


def searchSongs(title, artist, album, _country='US'):
    headers = _headers(_country)
    # TODO - clean up album and title a little (Remix, Deluxe Edition etc.)
    query_string = "{} {} {}".format(title, artist, album)
    query = urlencode({"term": query_string, "entity": "song", "s": _storefront(_country)})
    try:
        resp = requests.get(
            "https://itunes.apple.com/search?{}".format(query), timeout=60, headers=headers)
        if resp.status_code == requests.codes.forbidden:
            # wait and re-try just once
            if verbose:
                # don't interupt progress dots
                logging.info("Hit 403 - Too many search requests, Delaying {}s.".format(delay))
            sleep(delay)
            resp = requests.get(
                "https://itunes.apple.com/search?{}".format(query), timeout=60, headers=headers)
        if verbose:
            logging.info("https://itunes.apple.com/search?{}".format(query))
            logging.info(resp.text)
        # response.text is [] if 403 forbidden
        results = json.loads(resp.text)

        return list(filter(
            # lambda res: res.get("wrapperType", "") == "track" and res.get("kind", "") == "song", results["results"]))
            # Return all results that qualify, handling key errors like a boss
            lambda res: res.get("wrapperType", "") == "track" and res.get("kind", "") == "song" and
                res.get("isStreamable", False) is True, results["results"]))
    except Exception as e:
        logging.error(e)
        return []


def displayCandidates(candidates, song, pageStart, nSongs):
    print("{:2} songs found. Please select from following candidates:".format(nSongs))
    print("{:2}) {:5}| {:20}| {:20}| {:15}\n".format(' #', 'Dist.', song['title'], song['artist'], song['album']))
    fmtStr = "{:2}) {:5.3f}| {:20}| {:20}| {:15}"
    for i, s in enumerate(candidates):
        d = get_tracks_distance(s["trackName"], s["artistName"], s["collectionCensoredName"],
            str(s['releaseDate']), song['title'],
            song['artist'], song['album'], song['release_date'])
        print(fmtStr.format(
            i + pageStart, d, s["trackName"], s["artistName"], s["collectionCensoredName"]))


def selectSong(songs, desiredSong):
    nSongs = len(songs)
    page = 0
    pageSize = 10
    msg = "\nEnter candidates' number to select (default=0), 's' to skip this track."
    if nSongs > pageSize:
        msg += " 'n' to next page, 'p' to previous page.\n>>>_"
    else:
        msg += "\n>>>_"

    while True:
        start = page * pageSize
        end = start + pageSize
        # go to alternate screen
        os.system("tput smcup")
        print(chr(27) + "[2J")
        displayCandidates(songs[start:end], desiredSong, start, nSongs)
        ans = input(msg)
        logging.info("User ans = '{}'".format(ans))
        # print(chr(27) + "[2J")
        # go back to main screen
        os.system("tput rmcup")
        if ans.lower() == "s":
            print("Skiping track {}, {}".format(desiredSong["title"], desiredSong["artist"]))
            return None
        elif ans.lower() == "n":
            if page + 1 > int(nSongs / pageSize):
                pass
            else:
                page += 1
        elif ans.lower() == "p":
            if page == 0:
                pass
            else:
                page -= 1
        elif ans.isdigit():
            return songs[int(ans)]
        else:
            return songs[0]


def getBestMatch(title, artist, album, year):
    '''
    returns iTunes track closest in time-lexical space
    given title, artist, album and year
    None if no match or something went wrong
    '''
    songs = searchSongs(title, artist, album)
    if not songs:
        return None, None
    try:
        distance, match = get_best_match(title, artist, album, year, songs)
        if match is None:
            return None, None
        if verbose:
            logging.info(
                "Best match: {:6.4f}, {}, {}".format(
                    distance,
                    match['trackName'],
                    match['artistName'],
                    match['collectionName']))
        return distance, match

    except Exception as e:
        # Just return None if something went wrong
        logging.error(e)
        return None, None


def buildPlist(songs, treshold=0.4, _title="", _description=""):
    '''
    save playlist as xml for importing into iTunes matching each iTunes track
    with Spotify track best as possible.
    treshold - maximum acceptable time-lexical distance
    '''
    _tracks = {}
    _track_id = 10000
    for i, item in enumerate(songs['items']):
        tr = item['track']
        al = sp.album(tr['album']['id'])
        if verbose:
            # progress dot (this could be lenghty process)
            print('.', end='', flush=True)
        distance, match = getBestMatch(
            tr['name'], tr['artists'][0]['name'], tr['album']['name'], al['release_date'])
        if match is not None and distance < treshold:

            if download:
                path = "Music/{}.m4a".format(
                    slugify(
                        match['trackName'],
                        ok='-_()[]{}',
                        lower=False))
                url = match['previewUrl']
                save_sample(path, url)
                logging.info(
                    "Sample {} - {} downloaded to {}".format(match['artistName'], match['trackName'], path))
            if addToAM:
                resp = add_track_AM(match['trackId'])
                if resp == requests.codes.ok:
                    logging.info(
                        "Track {} - {} added to Apple Music".format(match['artistName'], match['trackName']))
                elif resp == requests.codes.not_found:
                    logging.info(
                        "Got 404 (Not Found) for track {}..".format(
                            tr['name']))
                elif resp == requests.codes.bad_request:
                    logging.info(
                        "Got 400 (Bad Request) for track {}.".format(
                            tr['name']))

            _tracks[str(_track_id)] = {
                "Track ID": match['trackId'],
                # "Track ID": _track_id,
                "Apple Music": True,
                "Artist": match['artistName'],
                "Album": match['collectionCensoredName'],
                "Bit Rate": 256,
                "Comments": "{}".format(tr['external_urls']['spotify']),
                "Disc Count": match['discCount'],
                "Disc Number": match['discNumber'],
                "Genre": match['primaryGenreName'],
                "Kind": "Apple Music AAC audio file",
                # "Location": "Remote",
                # "Location": "file:///Users/rrj/Documents/Python/Spotify-Downloader/" + path,
                "Name": match['trackName'],
                "Play Count": 0,
                "Playlist Only": True,
                "Sample Rate": 44100,
                # "Size": 255,
                "Sort Album": match['collectionName'],
                "Sort Artist": match['artistName'],
                "Sort Name": match['trackName'],
                "Total Time": match['trackTimeMillis'],
                "Track Number": match['trackNumber'],
                "Track Count": match['trackCount'],
                "Track Type": "Remote",
                "Year": arrow.get(match['releaseDate']).year
            }
            _track_id += 2

        # Allowance is 20 queries/minute - add small delay to avoid 403 from
        # itunes.com
        sleep(3)

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
