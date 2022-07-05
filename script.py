import os
from time import perf_counter
from datetime import datetime

from dotenv import load_dotenv

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import spotipy.util as util

import pandas as pd
from pathlib import Path

import json
import auth

load_dotenv()

sp = None

SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_CLIENT_CALLBACK_URL = 'http://localhost:3000/callback'
SPOTIFY_USERNAME = os.getenv('SPOTIFY_USERNAME')
SPOTIFY_PASSWORD = os.getenv('SPOTIFY_PASSWORD')
SPOTIFY_CLIENT_TOKEN = os.getenv('SPOTIFY_CLIENT_TOKEN')
SPOTIFY_OWNER_IDS = os.getenv('SPOTIFY_OWNER_IDS')

AUTH_SCOPE = [
  'playlist-read-private',
  'playlist-read-collaborative',
  'playlist-modify-public',
  'playlist-modify-private'
]
OWNER_IDS = SPOTIFY_OWNER_IDS.split(',')

# caps out at 50
PLAYLISTS_PER_CALL = 50

# caps out at 100
TRACKS_PER_CALL = 100

TRACK_FIELDS = [
  'limit',
  'offset',
  'next',
  'previous',
  'total',
  'items.added_at',
  'items.added_by.id',
  'items.track.id',
  'items.track.name',
  'items.track.duration_ms',
  'items.track.track_number',
  'items.track.type',
  'items.track.is_local',
  'items.track.album.id',
  'items.track.album.name',
  'items.track.album.release_date',
  'items.track.album.release_date_precision',
  'items.track.album.total_tracks',
  'items.track.album.type',
  'items.track.artists.id',
  'items.track.artists.name',
  'items.track.artists.type'
]

def check_env_vars():
  if (SPOTIFY_CLIENT_ID == None or len(SPOTIFY_CLIENT_ID) == 0):
    raise ValueError("SPOTIFY_CLIENT_ID must be provided")
  if (SPOTIFY_CLIENT_SECRET == None or len(SPOTIFY_CLIENT_SECRET) == 0):
    raise ValueError("SPOTIFY_CLIENT_SECRET must be provided")
  if (SPOTIFY_CLIENT_CALLBACK_URL == None or len(SPOTIFY_CLIENT_CALLBACK_URL) == 0):
    raise ValueError("SPOTIFY_CLIENT_CALLBACK_URL must be provided")
  if (SPOTIFY_USERNAME == None or len(SPOTIFY_USERNAME) == 0):
    raise ValueError("SPOTIFY_USERNAME must be provided")
  if (SPOTIFY_PASSWORD == None or len(SPOTIFY_PASSWORD) == 0):
    raise ValueError("SPOTIFY_PASSWORD must be provided")

def handle_auth():
  _sp = spotipy.Spotify()
  _sp.set_auth(get_authenticator().access_token)
  return _sp

def get_authenticator(): 
  spotify_authenticator = auth.SpotifyAuthenticator(
    client_id = SPOTIFY_CLIENT_ID,
    client_secret = SPOTIFY_CLIENT_SECRET,
    redirect_uri = SPOTIFY_CLIENT_CALLBACK_URL,
    username = SPOTIFY_USERNAME,
    password = SPOTIFY_PASSWORD,
    scope = ' '.join(AUTH_SCOPE)
  )
  spotify_authenticator.authorize()

  return spotify_authenticator

def fetch_playlist_items(playlist_id, limit = 100, offset = 0):
  return sp.playlist_items(playlist_id, ','.join(TRACK_FIELDS), limit, offset, None)

def fetch_all_playlist_tracks(playlist_id):
  # empty array to add tracks to this playlist
  playlist_items = []

  # initial request the first block of tracks from the playlist
  playlist_response = fetch_playlist_items(playlist_id, TRACKS_PER_CALL, 0)

  # add the tracks to the array
  playlist_items += playlist_response['items']

  # define the total tracks count
  total_tracks_count = playlist_response['total']

  # while the track count is less than the total tracks, keep hitting the API
  while len(playlist_items) < total_tracks_count:
    print('fetching ', TRACKS_PER_CALL, ' items per call with an offset of ', len(playlist_items), ' from playlist ', playlist_id)
    playlist_response_while = fetch_playlist_items(playlist_id, TRACKS_PER_CALL, len(playlist_items))
    playlist_items += playlist_response_while['items']
  
  # return the complete list of tracks for the playlist
  return playlist_items

def get_artists_data(artists):
  _artists = []
  for artist in artists:
    transformed_artist = {}
    transformed_artist['id'] = artist['id'] or 'null'
    transformed_artist['name'] = artist['name']
    transformed_artist['type'] = artist['type']
    _artists.append(transformed_artist)
  return _artists

# handle transformation of track information
def transform_tracks(tracks_data):
  transformed_tracks = []
  for track in tracks_data:
    transformed_track = {}
    the_track = track['track']

    transformed_track['added_at'] = track['added_at']
    transformed_track['added_by_id'] = track['added_by']['id']

    transformed_track['id'] = the_track['id'] or 'null'
    transformed_track['name'] = the_track['name']
    transformed_track['artists'] = get_artists_data(the_track['artists']) if 'artists' in the_track else []
    transformed_track['duration'] = the_track['duration_ms']
    transformed_track['track_number'] = the_track['track_number'] if 'track_number' in the_track else 0
    transformed_track['type'] = the_track['type'] if 'type' in the_track else 'null'
    transformed_track['is_local'] = the_track['is_local'] or False if 'is_local' in the_track else False
    transformed_tracks.append(transformed_track)
  return transformed_tracks

def transform_playlists(playlist_response):
  # empty array to add playlists to
  playlists_transformed = []

  for playlist in playlist_response['items']:
    playlist_minimal = {}
    playlist_minimal['owner_id'] = playlist['owner']['id']
    playlist_minimal['id'] = playlist['id']
    playlist_minimal['name'] = playlist['name']
    playlists_transformed.append(playlist_minimal)
  return playlists_transformed

def fetch_some_playlists():
  # empty array to add playlists to
  playlists = []

  # initial request the first block of playlists
  playlist_response = sp.current_user_playlists(PLAYLISTS_PER_CALL, 0)

  # add the tracks to the array
  playlists = transform_playlists(playlist_response)

  return playlists


def fetch_all_playlists():
  # empty array to add playlists to
  playlists = []

  # initial request the first block of playlists
  playlist_response = sp.current_user_playlists(PLAYLISTS_PER_CALL, 0)

  # add the tracks to the array
  playlists = transform_playlists(playlist_response)

  # define the total playlists count
  total_playlists_count = playlist_response['total']
  print(f"Total of {total_playlists_count} playlists to fetch");

  playlist_length = len(playlists)

  # while the track count is less than the total tracks, keep hitting the API
  while playlist_length < total_playlists_count:
    print(f"fetching {PLAYLISTS_PER_CALL} playlists per call with an offset of {playlist_length} from playlist")
    playlists_data = transform_playlists(sp.current_user_playlists(PLAYLISTS_PER_CALL, playlist_length))
    playlist_length += len(playlists_data)
    playlists += playlists_data
  
  # return the complete list of playlists 
  return playlists

def get_tracks_for_playlist(playlist):
  print(f"------ start '{playlist['name']}' {datetime.now()} ------")

  # fetch all the tracks for a given playlist id
  tracks_for_playlist = fetch_all_playlist_tracks(playlist['id'])

  # transform the tracks to only save the data we want
  transformed_tracks_for_playlist = transform_tracks(tracks_for_playlist)

  print(f"fetched all {len(transformed_tracks_for_playlist)} tracks for playlist '{playlist['name']}' {datetime.now()}")

  Path(f"./playlists/{playlist['owner_id']}").mkdir(
    parents = True,
    exist_ok = True
  )

  # convert and save a new csv file for each playlist
  # df = pd.json_normalize(transformed_tracks_for_playlist)
  # df.to_csv(f"./playlists/playlist-{playlist['id']}.csv")

  playlist_object = {};

  playlist_object = playlist;
  playlist_object['tracks'] = transformed_tracks_for_playlist;

  print(f"Saving {len(transformed_tracks_for_playlist)} tracks");
  with open(f"./playlists/{playlist['owner_id']}/playlist-{playlist['id']}.json", 'w', encoding='utf-8') as f:
    json.dump(
      playlist_object,
      f,
      ensure_ascii = False,
      indent = 2
    )
  print(f"------ end '{playlist['name']}' {datetime.now()} ------\n")


def main():
  # all_playlists_data = fetch_some_playlists();
  all_playlists_data = fetch_all_playlists()

  # # convert and save all playlists data
  df = pd.json_normalize(all_playlists_data)
  df.to_csv(f"playlists.csv", index = False)

  for item in all_playlists_data:
    # if OWNER_IDS are provided, filter the users saved/created playslists by the ids, otherwise, backup all playlists
    if len(OWNER_IDS) == 0 or ((item['owner_id'] in OWNER_IDS) or 'Your Top Songs' in item['name']):
      get_tracks_for_playlist(item)
      continue
    # print(f"Ignoring playlist '{item['name']}' because it is not created by the user. Created by '{item['owner_id']}'")

if __name__ == '__main__':
  t1_start = perf_counter()

  # Check we have the proper env vars before proceeding
  check_env_vars()

  sp = handle_auth()
  print("\n")
  main()
  t1_stop = perf_counter()
  print("Script completed in %.2f seconds" % (t1_stop - t1_start))