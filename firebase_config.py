"""
Firebase Admin SDK Configuration for Memory Sovereign
Centralized state management adhering to ecosystem constraints
"""

import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import json

# Initialize logger before imports to catch early errors
logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, storage
    from firebase_admin.exceptions import FirebaseError
except ImportError as e:
    logger.error(f"Firebase Admin SDK not installed: {e}")
    raise

class FirebaseConfig:
    """Singleton Firebase configuration manager with robust error handling"""
    
    _instance: Optional['FirebaseConfig'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseConfig, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.app = None
            self.db: Optional[firestore.Client] = None
            self.bucket = None
            self._config_path = Path(".env.firebase.json")
            self._initialize_firebase()
            self._initialized = True
    
    def _initialize_firebase(self) -> None:
        """Initialize Firebase with multiple fallback strategies"""
        
        # Strategy 1: Check for environment variable
        firebase_creds = os.getenv("FIREBASE_CREDENTIALS_JSON")
        
        # Strategy 2: Check for credentials file
        if not firebase_creds and self._config_path.exists():
            try:
                with open(self._config_path, "r") as f:
                    firebase_creds = f.read()
            except (IOError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to read firebase config file: {e}")
        
        # Strategy 3: Check for default Firebase config
        if not firebase_creds:
            default_paths = [
                "/etc/secrets/firebase-creds.json",
                "./firebase-creds.json",
                str(Path.home() / ".config/firebase/creds.json")
            ]
            
            for path in default_paths:
                if Path(path).exists():
                    try:
                        with open(path, "r") as f:
                            firebase_creds = f.read()
                        break
                    except (IOError, json.JSONDecodeError):
                        continue
        
        if not firebase_creds:
            logger.error("No Firebase credentials found. Using mock mode for development.")
            self._setup_mock_firebase()
            return
        
        try:
            # Parse and validate JSON
            creds_dict = json.loads(firebase_creds)
            
            # Validate required fields
            required_fields = ["type", "project_id", "private_key_id", "private_key"]
            for field in required_fields:
                if field not in creds_dict:
                    raise ValueError(f"Missing required field: {field}")
            
            # Initialize app
            cred = credentials.Certificate(creds_dict)
            
            # Check if app already exists
            if not firebase_admin._apps:
                self.app = firebase_admin.initialize_app(cred, {
                    'storageBucket': f"{creds_dict['project_id']}.appspot.com"
                })
            else:
                self.app = firebase_admin.get_app()
            
            self.db = firestore.client()
            self.bucket = storage.bucket()
            
            logger.info(f"Firebase initialized for project: {creds_dict['project_id']}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in Firebase credentials: {e}")
            self._setup_mock_firebase()
        except ValueError as e:
            logger.error(f"Invalid Firebase credentials: {e}")
            self._setup_mock_firebase()
        except FirebaseError as e:
            logger.error(f"Firebase initialization error: {e}")
            self._setup_mock_firebase()
    
    def _setup_mock_firebase(self) -> None:
        """Setup mock Firebase for development/testing"""
        logger.warning("Using mock Firebase client (data will be stored locally)")
        self.db = None
        self.bucket = None
        
        # Create local storage directory
        local_storage = Path("./local_firebase_storage")
        local_storage.mkdir(exist_ok=True)
    
    def get_document(self, collection: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Safely retrieve document with error handling"""
        if