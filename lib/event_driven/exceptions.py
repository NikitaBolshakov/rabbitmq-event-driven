class ModelException(Exception): # ACK events
    pass

class BusinessException(Exception): # ACK events
    pass

class TechnicalException(Exception): # NACK events
    pass

class ExternalServiceException(TechnicalException):
    pass
