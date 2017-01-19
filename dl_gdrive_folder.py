#!/usr/bin/python
from __future__ import print_function
import sys, httplib2, os, datetime, io, socket
from time import gmtime, strftime
from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools
from datetime import date
#########################################################################
# Made for Python 3.5 and Google Drive API v3.
# Usage: to replicate a Gogle Drive folder structure with all files, in your computer
# python dl_gdrive_folder.py <Google drive folder source> <local computer folder destination>
# Example:
# Folder Structure at Google Drive:
# F1
#	File0
#	F11
#		File1
#	F12
#		F211
#			FileA
#			FileB
# To download everything from folder F211 to a local folder TST
# python dl_gdrive_folder.py F211 TST	
# It doesn´t work if you have more than one folder with the same name
#########################################################################
# Build from the works of :
# Mark Culhane - google_drive_backup.py
# https://github.com/markz0r/tools/blob/master/backup_scripts/google_drive_backup.py
# and
# HatsuneMiku - recursive navigation over folders
# http://stackoverflow.com/questions/22092402/python-google-drive-api-list-the-entire-drive-file-tree
# https://github.com/HatsuneMiku/googleDriveAccess
#
# Know Issues: 
#		- wasn´t downloading files if verbose was not used - fixed on 19/01/2017
#		- don´t work with Google "Forms" - fixed (simply skip those files)
#		- downloads trashed files - fixed (don´t even consider them)
#########################################################################

#########################################################################
# Pre-requisites - Authorize API usage on google drive, and download/install google drive pyhton api. 
# Follow instructions on : https://developers.google.com/drive/v3/web/quickstart/python
# To install python client on windows:
# pip install --upgrade google-api-python-client
# Authorize API https://developers.google.com/drive/v3/web/quickstart/python#step_1_turn_on_the_api_name
# Download the client_secret.json to same dir as this script
#########################################################################


CLIENT_SECRET_FILE = 'client_secret.json'
TOKEN_FILE="drive_api_token.json"
SCOPES = 'https://www.googleapis.com/auth/drive'
APPLICATION_NAME = 'Drive File API - Python'
FOLDER_TYPE = 'application/vnd.google-apps.folder'
to_dir=str(date.today())+"_drive_backup"
global num_files
global num_skiped

try:
	import argparse
	parser = argparse.ArgumentParser(parents=[tools.argparser], description="Google Drive folder and files download")
	parser.add_argument("dir_from", type=str, help="Google Drive folder tree starting folder to be downloaded")
	parser.add_argument("dir_to", type=str, help="Initial local folder to receive tree and files")
	parser.add_argument("-l", "--lista", help="Just list folder and files to be downloaded. Don´t actually donwnload anything", action="store_true")
	parser.add_argument("-v", "--verbose", help="Writes what it´s doing.", action="store_true")
	args = parser.parse_args()
	from_dir = args.dir_from
	to_dir = args.dir_to
except ImportError:
	print("argparse Error!")
	args = None

def get_credentials():
	home_dir = os.path.expanduser('~')
	credential_dir = os.path.join(home_dir, '.credentials')
	if not os.path.exists(credential_dir):
		os.makedirs(credential_dir)
	credential_path = os.path.join(credential_dir, TOKEN_FILE)
	store = oauth2client.file.Storage(credential_path)
	credentials = store.get()
	if not credentials or credentials.invalid:
		flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
		flow.user_agent = APPLICATION_NAME
		if args:
			credentials = tools.run_flow(flow, store, args)
		else: # Needed only for compatibility with Python 2.6
			credentials = tools.run(flow, store)
		print("Storing credentials to {}".format(credential_path))
	return credentials

def prepDest(folder, spaces):
	if not os.path.exists(folder):
		if args.lista:
			print("{} Will create folder: {}".format(spaces, folder))
		else:
			if args.verbose:
				print("{} Creating folder: {}".format(spaces, folder))
			os.makedirs(folder)
			return True
	else:
		print("{} Folder {} already exists".format(spaces, folder))
	return False

def downloadFile(service, spaces, file_name, file_id, mimeType, dest_folder):
# Function that performs the download of each file to the specified local folder
	global num_skiped
	valid = True
	if (args.lista):
		print("{} downloading file: {}, to folder {} \n".format(spaces, file_name, dest_folder))
	else:
		if args.verbose:
			print("{} downloading file: {}, to folder {} \n".format(spaces, file_name, dest_folder))
		request = service.files().get_media(fileId=file_id)
		if "application/vnd.google-apps" in mimeType:
			if args.verbose:
				print("Google apps media types will be exported accordingly")
			if "form" in mimeType:
				print("Google app Form: {} - cannot be downloaded. Skiping...".format(file_name))
				valid = False
				num_skiped += 1
			elif "document" in mimeType:
				request = service.files().export_media(fileId=file_id, mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
				file_name = file_name + ".docx"
			elif "spreadsheet" in mimeType:
				request = service.files().export_media(fileId=file_id, mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
				file_name = file_name + ".xlsx"	
			elif "presentation" in mimeType:
				request = service.files().export_media(fileId=file_id, mimeType='application/vnd.openxmlformats-officedocument.presentationml.presentation')
				file_name = file_name + ".pptx"	
			else: 
				request = service.files().export_media(fileId=file_id, mimeType='application/pdf')
				file_name = file_name + ".pdf"
		if valid:			
			print("{}Downloading -- {}".format(spaces, file_name))
			response = request.execute()
			with open(os.path.join(dest_folder, file_name), "wb") as wer:
				if args.verbose:
					print("Writing file {} to folder {}.\n".format(file_name, dest_folder))
				wer.write(response)
				global num_files
				num_files +=1

def getFolderId(service, folderName):
	query = "name contains '%s' and mimeType = '%s'" % (folderName, FOLDER_TYPE)
	fid = None
	if args.verbose:
		print("Checking source folder existence: {}".format(folderName))
	result = service.files().list(q=query,
			   pageSize=10, pageToken='', fields="nextPageToken,files(parents,id,name,mimeType)").execute()
	if args.verbose:
		print("Result: {}".format(result))
	if len(result['files'])==0:
		print("Folder NOT found")
	else: 
		folder = result.get('files')[0]
		fid = folder['id']
		if args.verbose:
			print("Found {} folders with this name".format(len(result.get('files'))))
			print("Found folder! Id: {}".format(fid))
			print("Name: {}".format(folder['name']))
			for p in folder['parents']:
				print("Parent : {}".format(p))
	return(fid)

def getlist(ds, q, **kwargs):
	result = None
	npt = ''
	while not npt is None:
		if npt != '': kwargs['pageToken'] = npt
		entries = ds.files().list(q=q, **kwargs).execute()
		if result is None: result = entries
		else: result['files'] += entries['files']
		npt = entries.get('nextPageToken')
	return result	
	
def getFolderFiles(service, folderId, folderName, dest_folder, depth):
	# recursive function that walks down the folder tree creating the local folders and downloading the files
	spaces = ' ' * depth
	d_folder = dest_folder +  "\\" + folderName
	prepDest(d_folder, spaces)	
	if (args.lista or args.verbose):
#		print('%s+%s\n%s	 %s\n' % (spaces, folderId, spaces, folderName))
		print("{}+{}\n{}     {}\n".format(spaces, folderId, spaces, folderName))
	else:
		print("Source Folder: {}\n".format(folderName))
		

	# searching only for folders
	query = "'%s' in parents and mimeType='%s' and trashed = false" % (folderId, FOLDER_TYPE)
	entries = getlist(service, query, **{'pageSize': 1000})
	for folder in entries['files']:
		getFolderFiles(service, folder['id'], folder['name'], d_folder, depth+1)
	
	# searching only for files (notice que query is mimTye != FOLDER_TYPE
	query = "'%s' in parents and mimeType!='%s' and trashed = false" % (folderId, FOLDER_TYPE)
	entries = getlist(service, query, **{'pageSize': 1000})
	for f in entries['files']:
		if (args.lista or args.verbose):
#			print('%s -ID: %s NAME: %s TYPE: %s' % (spaces, f['id'], f['name'], f['mimeType']))
			print("{} -ID: {} NAME: {} TYPE: {}".format(spaces, f['id'], f['name'], f['mimeType']))
		downloadFile(service, spaces, f['name'], f['id'], f['mimeType'], d_folder)
	print("{} files downloaded so far\n".format(num_files))
		
		

		
def main(basedir):
	global num_files
	num_files = 0
	global num_skiped
	num_skiped = 0

	print("Downloading folder and files from: {} -> to: {}".format(from_dir, to_dir))
	print("Connecting with Google Drive")

	try:
		credentials = get_credentials()
		http = credentials.authorize(httplib2.Http())
		service = discovery.build('drive', 'v3', http=http)	
	except Exception: 
		print("Error connecting to Google Drive")
	else:
	
		print("Connected. Now let´s read the files")
		if args.lista:
			print("just listing folder and files from source")
			prepDest(to_dir, "")
			folderId = getFolderId(service, from_dir)
			if not folderId is None:
				getFolderFiles(service, folderId, from_dir, to_dir, 0)
			else:
				print("Aborting. Source folder {} not found".format(from_dir))

		elif prepDest(to_dir, ""):
			print("Downloading files")
			folderId = getFolderId(service, from_dir)
			if not folderId is None:
				getFolderFiles(service, folderId, from_dir, to_dir, 0)
				print("{} total files downloaded.\n".format(num_files))
				if num_skiped>0:
					print("{} total skiped files, not downloaded.".format(num_skiped))
			else:
				print("Aborting. Source folder {} not found".format(from_dir))
		else:
			print("Destination folder : {} - already exists".format(to_dir))


if __name__ == '__main__':
	main(os.path.dirname(__file__))
