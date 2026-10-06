import logging
import sys
import contextvars
try:
    from pythonjsonlogger import json as jsonlogger  # python-json-logger >= 3
except ImportError:  # pragma: no cover
    from pythonjsonlogger import jsonlogger

# Context variables for logging correlation
correlation_id_var = contextvars.ContextVar('correlation_id', default=None)
document_id_var = contextvars.ContextVar('document_id', default=None)
job_id_var = contextvars.ContextVar('job_id', default=None)

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Ensure timestamp and level are standard
        if not log_record.get('timestamp'):
            log_record['timestamp'] = self.formatTime(record, self.datefmt)
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname
            
        log_record['service'] = "clinextract-backend"
        
        # Add context vars if they exist
        corr_id = correlation_id_var.get()
        if corr_id:
            log_record['correlation_id'] = corr_id
            
        doc_id = document_id_var.get()
        if doc_id:
            log_record['document_id'] = doc_id
            
        job_id = job_id_var.get()
        if job_id:
            log_record['processing_job_id'] = job_id
            
        # Optional fields passed via extra parameter
        if hasattr(record, 'event'):
            log_record['event'] = record.event
        if hasattr(record, 'extractor'):
            log_record['extractor'] = record.extractor
        if hasattr(record, 'provider'):
            log_record['provider'] = record.provider
        if hasattr(record, 'latency_ms'):
            log_record['latency_ms'] = record.latency_ms

def setup_logging():
    logger = logging.getLogger()
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    logHandler = logging.StreamHandler(sys.stdout)
    # Define fields to include in the output JSON
    formatter = CustomJsonFormatter('%(timestamp)s %(level)s %(message)s %(module)s')
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)
    logger.setLevel(logging.INFO)
    
    # Silence third-party loggers that might leak info
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    return logger

def get_logger(name):
    return logging.getLogger(name)
