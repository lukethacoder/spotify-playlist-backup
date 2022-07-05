import os
import sys
import urllib.parse
import requests
import base64
import json
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions

from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.service import Service as FirefoxService

class SpotifyAuthenticator():

  def __init__(
    self,
    client_id,
    client_secret,
    redirect_uri,
    username,
    password,
    scope
  ):
    # Assign appropriate data to object attributes
    self.username = username
    self.password = password
    self.client_secret = client_secret
    self.client_id = client_id
    self.redirect_uri = redirect_uri
    self.scope = scope
    self.state = ''
    self.show_dialog = ''
    self.auth_code = ''
    self.tokens = {}
    self.access_token = ''
    self.refresh_token = ''

  def get_auth_code(self, headless = True):
    # Define base url for authorization site and define response type
    auth_url_base = 'https://accounts.spotify.com/authorize?'
    response_type = 'code'

    # Create payload based on data from config file extracted during __init__
    payload = {
      'client_id': self.client_id,                   
      'redirect_uri': self.redirect_uri,                   
      'response_type': response_type,                   
      'scope': self.scope
    }

    # Encode the payload for a url and append to the base url
    url_params = urllib.parse.urlencode(payload)
    full_auth_url = auth_url_base + url_params
    print('Custom authorization url:', full_auth_url, '\n')

    print('Directing to Spotify Authorization page...')

    # Create selenium options
    options = FirefoxOptions()
    options.headless = headless

    # Create selenium driver
    driver = webdriver.Firefox(
      service = FirefoxService(GeckoDriverManager().install()),
      options = options
    )

    # Open browser
    driver.get(full_auth_url)

    # Find html form fields
    login_field = driver.find_element(By.ID, 'login-username')
    pass_field = driver.find_element(By.ID, 'login-password')
    sub_button = driver.find_element(By.ID, 'login-button')

    print('Submitting user login data...\n')

    print(f"Username ({self.username}) length of {len(self.username)}")
    print(f"Password (******) length of {len(self.password)}")

    # Pass user data to form
    login_field.send_keys(self.username)
    pass_field.send_keys(self.password)

    print('Sent keys...\n')

    # Selenium raises an error when you can't connect to a domain
    # Catch that error to handle it and extract the URL for the access token.
    try:
      # Submit the form
      sub_button.click()
      print('sub_button click...\n')

      # pause for redirect to acceptance page
      time.sleep(3)

      # Find agree button
      # driver.find_element_by_id('auth-accept')
      agree_button = driver.find_element('[data-testid="auth-accept"]')
      print('Button Found')

      # Click button and wait for error
      agree_button.click()
      print('Button Clicked')
      time.sleep(30)
    except Exception as err:
      # Catch error and do nothing to keep code going
      print('Error caught')
      print('Redirect successful...\n')
      print('Extracting authorization code now...\n')

    time.sleep(5)

    # Get current url which now contains the access token 
    redirect = driver.current_url
    driver.close()

    print('Redirect-URI:', redirect)

    parsed = urllib.parse.urlparse(redirect)
    return_package = urllib.parse.parse_qs(parsed.query)

    # Return the query from the rediret url
    return return_package['code'][0]

  def get_tokens(self, grant_type = 'authorization_code'):
    # Check for lack of appropriate parameters
    if not self.auth_code:
      print('No authorization code provided!')
      sys.exit(1)
    elif not self.redirect_uri:
      print('Please put a redirect URI in the config file')
      sys.exit(1)
    elif not self.client_id:
      print('No client id provided!')
      sys.exit(1)
    elif not self.client_secret:
      print('No client secret provided!')
      sys.exit(1)

    # Generate body for request to get access token
    body = {
      'grant_type': grant_type,
      'code': self.auth_code,
      'redirect_uri': self.redirect_uri
    }

    # Format client id and secret for request header + encode them
    client_params = self.client_id + ':' + self.client_secret
    encoded_client_params = base64.b64encode(client_params.encode('ascii'))

    print('\nLoading Client Secret, Client ID, and Authorization Pay Load...')

    # Create header with encoded client id and secret
    headers = {'Authorization': 'Basic ' + encoded_client_params.decode('ascii')}

    print('\nRequesting Access and Refresh Tokens...')

    # Submit post request to get the access tokens
    response = requests.post(
      'https://accounts.spotify.com/api/token',
      data = body,
      headers = headers
    )

    tokens = response.text

    print('\nParsing and extracting tokens...')
    return json.loads(tokens)

  def token_refresh(self, grant_type = 'refresh_token'):
    body = {
      'grant_type':grant_type,
      'refresh_token': os.getenv('SPOTIFY_CLIENT_REFRESH_TOKEN')
    }

    client_params = self.client_id + ':' + self.client_secret
    encoded_client_params = base64.b64encode(client_params.encode('ascii'))
    headers = {'Authorization': 'Basic ' + encoded_client_params.decode('ascii')}

    response = requests.post(
      'https://accounts.spotify.com/api/token',
      data = body,
      headers = headers
    )

    tokens = response.text
    tokens_parsed = json.loads(tokens)

    os.environ["SPOTIFY_CLIENT_TOKEN"] = tokens_parsed['access_token']
    self.access_token = tokens_parsed['access_token']
    print(f"Set env var SPOTIFY_CLIENT_TOKEN with value {os.getenv('SPOTIFY_CLIENT_TOKEN')}")

    return True

  def authorize(self):
    print('\nAttempting to authorize...\n')
    authorized = os.getenv('SPOTIFY_CLIENT_AUTHORIZED') or 'false'
    # config.get('tokens','authorized?')

    if authorized.lower() == 'false':
      print('\nRunning fresh authorization protocol...')
      self.auth_code = self.get_auth_code(headless = True)
      tokens = self.get_tokens()
      self.tokens = tokens

      self.access_token = self.tokens['access_token']
      self.refresh_token = self.tokens['refresh_token']

      os.environ["SPOTIFY_CLIENT_TOKEN"] = self.tokens['access_token']
      os.environ["SPOTIFY_CLIENT_REFRESH_TOKEN"] = self.tokens['refresh_token']
      os.environ["SPOTIFY_CLIENT_LAST_REFRESH_TIME"] = str(time.time())
      os.environ["SPOTIFY_CLIENT_AUTHORIZED"] = 'true'
    else:
      # Check time since last refresh
      current_time = int(time.time())
      last_refresh_time = float(os.getenv('SPOTIFY_CLIENT_LAST_REFRESH_TIME'))
      delt = current_time - last_refresh_time

      if delt >= 3000:
        print('\nRefreshing access token...')
        self.token_refresh()
        # self.tokens['access_token'] = config.get('tokens','access_token')

        os.environ["SPOTIFY_CLIENT_TOKEN"] = None
        os.environ["SPOTIFY_CLIENT_LAST_REFRESH_TIME"] = str(time.time())
      else:
        print('\nNo authorization needed...')
        self.access_token = os.getenv('SPOTIFY_CLIENT_TOKEN')
        self.tokens['access_token'] = os.getenv('SPOTIFY_CLIENT_TOKEN')
        self.tokens['refresh_token'] = os.getenv('SPOTIFY_CLIENT_REFRESH_TOKEN')
        pass

    return True