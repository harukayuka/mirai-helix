"""
Utility untuk pembersihan file-file lama.
Mencegah kebocoran disk dan memory akibat penumpukan data.
"""
import os
import glob
import time
import logging

logger = logging.getLogger('mirai-helix.cleanup')

def clean_old_reports(directory: str = "data/qwen_results", days_to_keep: int = 7):
    """
    Hapus file laporan older dari X hari.
    
    Args:
        directory: Direktori tempat file laporan disimpan.
        days_to_keep: Jumlah hari file dipertahankan sebelum dihapus.
    """
    if not os.path.exists(directory):
        logger.debug(f"Directory {directory} tidak ada, skip cleanup.")
        return

    cutoff_time = time.time() - (days_to_keep * 86400)  # 86400 detik/hari
    deleted_count = 0
    
    try:
        # Cari semua file qwen_report_*.txt
        pattern = os.path.join(directory, "qwen_report_*.txt")
        for filepath in glob.glob(pattern):
            if os.path.getmtime(filepath) < cutoff_time:
                os.remove(filepath)
                deleted_count += 1
                logger.info(f"Deleted old report: {os.path.basename(filepath)}")
        
        if deleted_count > 0:
            logger.info(f"Cleanup complete: {deleted_count} old reports removed.")
        else:
            logger.debug("No old reports to clean up.")
            
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def clean_old_user_data(directory: str = "data/qwen_user", days_to_keep: int = 30):
    """
    Hapus file data user lama (opsional, untuk mencegah penumpukan).
    
    Args:
        directory: Direktori tempat file user disimpan.
        days_to_keep: Jumlah hari data user dipertahankan.
    """
    if not os.path.exists(directory):
        return

    cutoff_time = time.time() - (days_to_keep * 86400)
    deleted_count = 0
    
    try:
        pattern = os.path.join(directory, "*.txt")
        for filepath in glob.glob(pattern):
            if os.path.getmtime(filepath) < cutoff_time:
                os.remove(filepath)
                deleted_count += 1
                logger.info(f"Deleted old user data: {os.path.basename(filepath)}")
        
        if deleted_count > 0:
            logger.info(f"User data cleanup complete: {deleted_count} files removed.")
            
    except Exception as e:
        logger.error(f"Error during user data cleanup: {e}")
