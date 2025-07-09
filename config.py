--- a/config.py
+++ b/config.py
@@
 # Optional Google Drive RAG credentials loaded via DRIVE_CRED_JSON and DRIVE_FOLDER_ID
-drive_service = None
-FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")
-_creds_json = os.getenv("DRIVE_CRED_JSON")
+drive_service = None
+FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")
+# Either a JSON string or a path on disk to the service-account file:
+creds_json = os.getenv("DRIVE_CRED_JSON")
+creds_path = os.getenv("DRIVE_CRED_PATH")

 if FOLDER_ID and (creds_json or creds_path):
     try:
-        creds_info = json.loads(_creds_json)
+        if creds_json:
+            creds_info = json.loads(creds_json)
+        else:
+            with open(creds_path, "r", encoding="utf-8") as f:
+                creds_info = json.load(f)
         creds = service_account.Credentials.from_service_account_info(
             creds_info,
             scopes=["https://www.googleapis.com/auth/drive.readonly"]
         )
         drive_service = build("drive", "v3", credentials=creds)
         logger.info("Google Drive RAG enabled.")
     except Exception as e:
         drive_service = None
         logger.warning(f"Google Drive RAG disabled: {e}")
 else:
     logger.info("Google Drive RAG disabled (missing folder ID or credentials)")
