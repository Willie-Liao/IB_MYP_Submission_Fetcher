import os
import time
import requests
from tqdm import tqdm


def download(files, dir='.', job_pool=None):
    """
    Download multiple files using a process pool.
    
    Args:
        files: List of dicts with 'name' and 'url' keys
        dir: Output directory
        job_pool: Multiprocessing pool for parallel downloads
    """
    if not dir.endswith('/'):
        dir += '/'
    
    download_tasks = []
    for file in files:
        download_tasks.append({
            'filepath': dir + file['name'],
            'url': file['url']
        })
    
    if download_tasks:
        results = list(tqdm(
            job_pool.imap(download_file, download_tasks),
            desc='Downloading ' + dir,
            total=len(download_tasks)
        ))
        
        # Summary
        downloaded = results.count(True)
        skipped = results.count('skipped')
        failed = results.count(False)
        tqdm.write(f"Download complete: {downloaded} new, {skipped} skipped, {failed} failed")


def download_file(file_info):
    """
    Download a single file with retry logic and skip if exists.
    
    Args:
        file_info: Dict with 'filepath' and 'url' keys
    Returns:
        True if downloaded, 'skipped' if already exists, False if failed
    """
    filepath = file_info['filepath']
    url = file_info['url']
    max_retries = 3
    
    # Skip if file already exists
    if os.path.exists(filepath):
        return 'skipped'
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, stream=True, timeout=120)
            response.raise_for_status()
            
            # Write to temp file first, then rename (safer)
            temp_filepath = filepath + '.tmp'
            with open(temp_filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Rename temp to final
            os.rename(temp_filepath, filepath)
            return True
            
        except Exception as e:
            # Clean up temp file if exists
            temp_filepath = filepath + '.tmp'
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            
            if attempt < max_retries - 1:
                tqdm.write(f"Retry {attempt + 1}/{max_retries} for {os.path.basename(filepath)}")
                time.sleep(3)  # Wait before retry
            else:
                tqdm.write(f"FAILED: {os.path.basename(filepath)} - {type(e).__name__}")
                return False
