from __future__ import print_function
import httplib2
import os
import io
import json
import datetime
import sys

from apiclient.http import MediaIoBaseDownload
from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

#Directory we are downloading structure and files 
today=str(datetime.datetime.now().strftime("%Y-%m-%d-%H%M"))
print(today, "This is the date") 
backup_dir='/home/giselle2/rccgoogledrive/rccgoogledrivebackup/googleapitest/files/' + today +"/" 
os.mkdir( backup_dir, 0755 );
# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/drive-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/drive.readonly'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Drive API Python Quickstart'
TOKEN_FILE = os.path.expanduser('~/.credentials/drive-python-quickstart.json')



#To empty out files folder for each exucution 

def get_credentials():
    """Gets valid user credentials from storage.
    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.
    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'drive-python-quickstart.json')
    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def main():
    """Shows basic usage of the Google Drive API.
    Creates a Google Drive API service object and outputs the names and IDs
    for up to 10 files.
    """ 
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)

    #Folder Structure creation 
    folder_items=[]
    page_token = None
    while True:
        results = service.files().list(q="mimeType='application/vnd.google-apps.folder'",
            fields="nextPageToken, files(id,name,mimeType,parents)",pageToken=page_token).execute()
        folder_items.extend(results.get('files', []))
        page_token = results.get('nextPageToken', None)
        if page_token is None:
            break;

#Defined all_folder_dict keys= item id, dictionary values: 0=name 1=parents 2=path
    all_folder_dict={}
    for item in folder_items:
        if 'parents'in item:
            all_folder_dict[item['id']]=[item['name'], item['parents'], None]
        if not 'parents' in item:
            all_folder_dict[item['id']]=[item['name'], None, None] 
    
    for folder_id in all_folder_dict:
        orig_id=folder_id
        name, parents, path= all_folder_dict[folder_id]
        path=name+'/'
        if parents:
            parent_id=parents[0]
            has_parent=1
            while has_parent:
                try:
                    prev_parent_id=all_folder_dict[parent_id][1][0]
                    prev_parent_name=all_folder_dict[parent_id][0]
                    prev_parent_name=prev_parent_name.replace("/", "-")
                    path=prev_parent_name+'/'+path
                    parent_id=prev_parent_id
                except (TypeError,KeyError) as e:
                    try:
                        os.makedirs(backup_dir+path)
                    except OSError:
                        pass
                    all_folder_dict[orig_id][2]=backup_dir+path
                    has_parent=0
        if not parents:
            try:
                os.makedirs(backup_dir+path)
            except OSError:
                pass     
            all_folder_dict[orig_id][2]=backup_dir+path            

                    
    #Downloading Files Section
    items=[]
    page_token = None
    while True:
        results = service.files().list(q="mimeType!='application/vnd.google-apps.folder'", fields="nextPageToken, files(id,name,mimeType,parents)",pageToken=page_token).execute()
        items.extend(results.get('files', []))
        page_token = results.get('nextPageToken', None)
        if page_token is None:
            break;        

    if not items:
        print('No files found.')
    else:
        print('Files:')
        for item in items:
            print('{0} ({1}--{2})'.format(item['name'].replace("/", "-").encode('utf8'), item['id'], item['mimeType'] ))
            file_id = item['id'] #add file id File_Mimetype
            file_mimetype = item ['mimeType']  
            if file_mimetype == "application/vnd.google-apps.folder":
                continue
            elif file_mimetype == "application/vnd.google-apps.file":
                request = service.files().export_media(fileId=file_id)
            elif file_mimetype == "application/vnd.google-apps.spreadsheet":
                mime_Type='application/x-vnd.oasis.opendocument.spreadsheet'
                request = service.files().export_media(fileId=file_id, mimeType=mime_Type)
                file_name = item ['name']+'.xlsx'
            elif file_mimetype == "application/vnd.google-apps.document":
                mime_Type= 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                request = service.files().export_media(fileId=file_id, mimeType=mime_Type)
                file_name = item ['name']+'.docx'
            elif file_mimetype == "application/vnd.google-apps.presentation":
                mime_Type= 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                request = service.files().export_media(fileId=file_id, mimeType=mime_Type)
                file_name = item ['name']+'.ppt'
            elif file_mimetype == "application/vnd.google-apps.form":
                continue
            else:
                request = service.files().get_media(fileId=file_id) 
                file_name = item ['name']

            file_name = file_name.replace("/", "-")
            try:
                folder_path=all_folder_dict[item['parents'][0]][2]
            except KeyError:
                #print('***No parent in dictionary, skipping for now***')
                #continue #Skipping shared files come back later
		folder_path = backup_dir

	    file_path = folder_path+file_name

            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request, chunksize=10*1024*1024)
            done = False
            count = 0
	    too_large = 0 
            while done is False:
                count += 1
		try:
                    status, done = downloader.next_chunk()
		except:
		    too_large = 1
		    print('This file is too large to be exported')
		    break
                print('Download {0}%.'.format(str(int(status.progress() * 100))))
                if count == 5 and int(status.progress() * 100) == 0 :
		    print('Downloading with curl')
		    credentials = get_credentials()
		    token_data = json.load(open(TOKEN_FILE)) 
		    curl_cmd = 'curl -X GET -sSL -H "Authorization: Bearer '+token_data['token_response']['access_token']+'" -o "'+file_path+'" "https://www.googleapis.com/drive/v3/files/'+file_id+'/export?mimeType='+mime_Type+'"'
		    os.system(curl_cmd)
                    break
            if count == 5 or too_large == 1:
                continue
            else :
                file_content=fh.getvalue()

            file_content=fh.getvalue()
            with open(file_path, 'wb') as f:
                f.write(file_content)

if __name__ == '__main__':

    main()  

