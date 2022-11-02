import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import base64
import json
import datetime
import pickle
import os.path
from conf.config import BASE_URL,CLIENT_ID,CLIENT_SECRET
from logger import get_logger

#global variables
accessToken = ''
refreshToken = ''
expiresAt = ""
refreshExpiresAt = ""
checkpoints = {'account_scoring_last_checkpoint': '', 'account_detection_last_checkpoint': '','audits_last_checkpoint': ''}
checkpoint_filename = 'checkpoints.pickle'
tokens_filename = 'tokens.pickle'
tokens = {'accessToken': '', 'expiresAt': '', 'refreshToken': '', 'refreshExpiresAt': ''}


#logger
LOG = get_logger("vectra-saas-pull",stream_level='DEBUG')



def retry_session(retries, session=None, backoff_factor=0.3):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def AuthManager():
    '''
    This function is making sure there is a valid accessToken to use
    '''
    
    credsLoadedFromFile = False
    
    #no existing token in global variables or store locally
    if not os.path.exists(tokens_filename) and accessToken == '':
        
        LOG.info(f'No existing tokens found ({ tokens_filename } does not exist). Initiating authentication.. ')
        
        authenticate()
        
    elif os.path.exists(tokens_filename) and accessToken == '':
        
        #loading stored information
        LOG.info(f'Loading saved tokens')
        loadSavedTokens()
        credsLoadedFromFile = True  
       
    if accessToken != '' or credsLoadedFromFile == True:
        
        #access token exists - still valid?
        now = datetime.datetime.utcnow()
        format = '%Y-%m-%d %H:%M:%S.%f'
        token_exp = datetime.datetime.strptime(str(expiresAt), format)
        refresh_token_exp = datetime.datetime.strptime(str(refreshExpiresAt), format)
        if now > token_exp and now > refresh_token_exp:
            
            #all expired - get new token
            LOG.info(f'All tokens expired - Initiating new authentication')
            authenticate()
            
        elif now > token_exp and now < refresh_token_exp:
            
            #refresh token still valid - getting a new token
            LOG.info(f'Token has expired at { expiresAt } (current UTC Time: { now }) - Using refresh token to get a new token')
            refresh_auth()
            
        else:
            
            LOG.info(f'Access token is still valid! Expire at { expiresAt } (current UTC time: { now})')
            
    else:
        
        LOG.debug(f'New tokens have just been created. All set!')
    

def authenticate():
    '''
    Authenticate to SaaS API
    '''
    
    global accessToken
    global refreshToken
    global expiresAt
    global refreshExpiresAt
    
    url = BASE_URL+"oauth2/token"

    auth_string = CLIENT_ID+':'+CLIENT_SECRET
    auth_string_base64 = base64.b64encode(auth_string.encode('ascii'))

    payload='grant_type=client_credentials'
    headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'application/json',
    'Authorization': 'Basic '+auth_string_base64.decode('ascii')
    }
    
    LOG.debug(f'OAuth query: { url } with payload { payload }')
    
    try:
        
        session = retry_session(retries=5)
        response = session.post(url=url, data=payload, headers=headers)
        #LOG.error(response.raise_for_status())
        
        LOG.debug(f'{ response }')
        
        accessToken = response.json()['access_token']
        expiresAt = str(datetime.datetime.utcnow() + datetime.timedelta(seconds=response.json()['expires_in']))
        refreshToken = response.json()['refresh_token']
        refreshExpiresAt = str(datetime.datetime.utcnow() + datetime.timedelta(seconds=response.json()['refresh_expires_in']))
        
        LOG.info(f'Access Token: { accessToken}')
        LOG.info(f'Access Token expires at: { expiresAt }')
        LOG.info(f'Refresh Token: { refreshToken}')
        LOG.info(f'Refresh Token expires at: { refreshExpiresAt }')
        
        saveTokens()
            
    except requests.exceptions.TooManyRedirects:
        
        LOG.error(f'Too many redirect. Check the URL: { url }')
        
    except requests.exceptions.RequestException as e:
        
        LOG.error(f'Request Error: { e }')
        raise SystemExit(e)
    
    
def refresh_auth():
    '''
    get new access token with refresh token
    '''
    
    global accessToken
    global expiresAt
    
    auth_string = CLIENT_ID+':'+CLIENT_SECRET
    auth_string_base64 = base64.b64encode(auth_string.encode('ascii'))
    
    url = BASE_URL+"oauth2/token"

    payload=f'grant_type=refresh_token&refresh_token={refreshToken}'
    headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'application/json'
    }
    
    try:
        
        session = retry_session(retries=5)
        response = session.post(url=url, data=payload, headers=headers)

        #response = requests.request("POST", url, headers=headers, data=payload)
        
        LOG.debug(response.json())
        
        #store new value
        accessToken = response.json()['access_token']
        expiresAt = str(datetime.datetime.utcnow() + datetime.timedelta(seconds=response.json()['expires_in']))
        
        LOG.info(f'New access Token: { accessToken}')
        LOG.info(f'New access Token expires at: { expiresAt }')
        
        #save to disk
        saveTokens()
        
    except requests.exceptions.TooManyRedirects:
        
        LOG.error(f'Too many redirect. Check the URL: { url }')
        
    except requests.exceptions.RequestException as e:
        
        LOG.error(f'Request Error: { e }')
        raise SystemExit(e)
    
    
def getCurrentCheckpoint(endpoint):
    '''
    get latest checkpoint
    '''
    
    global checkpoints
    
    #get valid token
    AuthManager()
    
    url = f'{ BASE_URL }api/v3/events/{ endpoint }'
    #query with very high value
    params = {'limit': '100', 'from': '10000000' }
    headers = {'Authorization': 'Bearer '+accessToken}

    try:
        response = requests.request("GET", url, params=params, headers=headers)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise SystemExit(err)
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)
    
    chkpt = response.json()['next_checkpoint']
    LOG.info(f'latest checkpoint for { endpoint } is { chkpt }')
    
    #just look at the last 100 events
    if endpoint == 'account_detection':
        
        checkpoints['account_detection_last_checkpoint'] = chkpt - 100
        return 
        
    elif endpoint == 'account_scoring':
        
        checkpoints['account_scoring_last_checkpoint'] = chkpt - 100
        return 
        
    elif endpoint == 'audits':
        
        checkpoints['audits_last_checkpoint'] = chkpt - 100
        return
        
    else:
        
        LOG.error(f'unknown endpoint { endpoint }')
        exit()
        
def loadSavedCheckpoint():
    '''
    load latest checkpoint saved
    '''
    
    global checkpoint_filename
    global checkpoints
    
    with open(checkpoint_filename, 'rb') as f:
        
        checkpoints = pickle.load(f)
    
def saveLastCheckpoint():
    '''
    save latest checkpoint on disk
    '''
    
    global checkpoint_filename
    global checkpoints
    
    with open(checkpoint_filename, 'wb') as f:
        
        pickle.dump(checkpoints, f)
        
        
def saveTokens():
    '''
    save token and refresh token (including expiry date) in a pickle file
    '''
    
    tokens = {'accessToken': accessToken, 'expiresAt': expiresAt, 'refreshToken': refreshToken, 'refreshExpiresAt': refreshExpiresAt}
    
    with open(tokens_filename, 'wb') as f:
        
        pickle.dump(tokens, f)
        
def loadSavedTokens():
    '''
    load Tokens saved on disk
    '''
    
    global accessToken
    global refreshToken
    global expiresAt
    global refreshExpiresAt
    global tokens
    
    with open(tokens_filename, 'rb') as f:
        
        tokens = pickle.load(f)
        
    accessToken = tokens['accessToken']
    expiresAt = tokens['expiresAt']
    refreshToken = tokens['refreshToken']
    refreshExpiresAt = tokens['refreshExpiresAt']
    
    printDict(tokens)
        
def printDict(dict):
    '''
    Generic function to print a dict
    '''    
    
    for key, value in dict.items():
        LOG.debug(f'{ key} : { value}')
        
    
def fetchEvents(checkpoint_id='',endpoint=''):
    '''
    get detections based on checkpoint - use SaaS v3 API
    '''
    
    global checkpoints   
    MORE_EVENT = True
    
    #check token
    AuthManager()
    
    #check endpoint value
    if endpoint not in ['account_detection','account_scoring','audits']:
        
        LOG.error(f'unknown endpoint { endpoint }. exiting..')
        exit()
    
    while MORE_EVENT:
        
        LOG.info(f'Fetching events from { endpoint } events with checkpoint = { checkpoint_id } ')
    
        url = f' {BASE_URL}api/v3/events/{endpoint}'
        params = {'limit': '100', 'from': checkpoint_id }
        
        headers = {
        'Authorization': 'Bearer '+accessToken
        }

        try:
            response = requests.request("GET", url, params=params, headers=headers)
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            raise SystemExit(err)
        except requests.exceptions.RequestException as e:
            raise SystemExit(e)
        
        
        #set next checkpoint and save the data
        det_chkpt = response.json()['next_checkpoint']
        
        if checkpoint_id == det_chkpt:
            
            LOG.info(f'No new events to ingest')
            MORE_EVENT = False
            
        else:
        
            #new events
            checkpoint_id = det_chkpt
            events_filename = f'vectra_logs/{endpoint}.json'
            LOG.info(f'saving events in file { events_filename }. Next checkpoint is { det_chkpt }')
            writeEvents(events_filename,json.dumps(response.json()))
        
            #check if there is more events to read
            if response.json()['remaining_count'] == 0:
                
                LOG.info(f'All events have been fecthed for endpoint { endpoint }')
                MORE_EVENT = False
                
                LOG.info(f'Saving Next checkpoint for { endpoint }: { det_chkpt }')
                keyname = f'{endpoint}_last_checkpoint'
                checkpoints[keyname] = det_chkpt
                saveLastCheckpoint()
                printDict(checkpoints)
                    
                   
    return True
    

def writeEvents(filename, data):
    '''
    append data in JSON format to the file
    '''
    
    data_json = json.loads(data)
    
    with open(filename,'a+') as file:
        # First we load existing data into a dict.
        #file_data = json.load(file) 
        for x in data_json['events']:  
            #print(x)
            file.writelines(str(json.dumps(x))+'\n')
            
        
def main():
    
    global checkpoints
    
    if BASE_URL == '' or CLIENT_ID == '' or CLIENT_SECRET == '':
        
        LOG.error(f'Configuration is not set. Edit config file! Exiting..')
        exit()
    
    if not os.path.exists(checkpoint_filename):
        
        LOG.info(f'file { checkpoint_filename } does not exist. Fetching current checkpoints')
        
        getCurrentCheckpoint('account_detection')
        getCurrentCheckpoint('account_scoring')
        getCurrentCheckpoint('audits')
        
        printDict(checkpoints)
        
    else:
        
        LOG.info(f'{ checkpoint_filename } has been found! Loading values..')
        loadSavedCheckpoint()
        printDict(checkpoints)
                
    
    #get detections
    fetchEvents(checkpoints['account_detection_last_checkpoint'],endpoint='account_detection')
    fetchEvents(checkpoints['account_scoring_last_checkpoint'],endpoint='account_scoring')
    fetchEvents(checkpoints['audits_last_checkpoint'],endpoint='audits')
    
    LOG.info(f'All events have been fetched. Exiting')
    

if __name__ == '__main__':
    
    main()