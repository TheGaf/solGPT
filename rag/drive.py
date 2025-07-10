import logging
from io import BytesIO
from googleapiclient.http import MediaIoBaseDownload
import PyPDF2
from helpers.text import split_text

def load_drive_docs(drive_service, folder_id):
    """
    Load and chunk documents from a Google Drive folder.

    Args:
        drive_service: Authenticated Drive API service instance.
        folder_id (str): ID of the Drive folder to load docs from.

    Returns:
        List[Tuple[str, str]]: List of (text_chunk, source_name) tuples.
    """
    results = []
    try:
        # List files in the specified folder
        query = f"'{folder_id}' in parents and trashed=false"
        response = drive_service.files().list(
            q=query,
            fields="files(id,name,mimeType)"
        ).execute()

        for f in response.get('files', []):
            file_id = f['id']
            name = f['name']
            mime = f['mimeType']
            content = ''

            # Download plain text files
            if mime == 'text/plain':
                request = drive_service.files().get_media(fileId=file_id)
                fh = BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                content = fh.getvalue().decode('utf-8', errors='ignore')

            # Download and parse PDFs
            elif mime == 'application/pdf':
                request = drive_service.files().get_media(fileId=file_id)
                fh = BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                fh.seek(0)
                reader = PyPDF2.PdfReader(fh)
                content = "\n".join(
                    page.extract_text() or '' for page in reader.pages
                )

            # Export Google Docs as plain text
            elif mime == 'application/vnd.google-apps.document':
                exported = drive_service.files().export(
                    fileId=file_id,
                    mimeType='text/plain'
                ).execute()
                content = exported.decode('utf-8', errors='ignore')
            else:
                # skip unsupported types
                continue

            # Chunk the content and record source name
            chunks = split_text(content)
            for chunk in chunks:
                results.append((chunk, name))

    except Exception as e:
        logging.warning(f"Drive RAG failed: {e}")

    return results
