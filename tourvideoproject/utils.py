import logging
from django.utils import timezone


class LoggerHelper:
    """
    A utility class to standardize logging across the application.
    """

    @staticmethod
    def get_logger(module_name):
        """
        Get a logger for the specified module.

        Args:
            module_name (str): The name of the module (typically the app name)

        Returns:
            logging.Logger: A configured logger instance
        """
        return logging.getLogger(module_name)

    @staticmethod
    def get_user_info(request):
        """
        Extract user information from the request.

        Args:
            request: The Django request object

        Returns:
            str: A string containing user information
        """
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"User ID: {request.user.id} | Email: {request.user.email}"
        return "Anonymous user"

    @staticmethod
    def get_request_info(request):
        """
        Extract request information.

        Args:
            request: The Django request object

        Returns:
            str: A string containing request information
        """
        return f"Method: {request.method} | Path: {request.path} | IP: {request.META.get('REMOTE_ADDR', 'unknown')}"

    @staticmethod
    def log_api_request(logger, request, message="API request received"):
        """
        Log an API request with standardized format.

        Args:
            logger (logging.Logger): The logger instance
            request: The Django request object
            message (str): Optional custom message
        """
        user_info = LoggerHelper.get_user_info(request)
        request_info = LoggerHelper.get_request_info(request)
        logger.info(f"{message} | {user_info} | {request_info}")

    @staticmethod
    def log_api_response(logger, request, status_code, message="API response sent"):
        """
        Log an API response with standardized format.

        Args:
            logger (logging.Logger): The logger instance
            request: The Django request object
            status_code (int): HTTP status code
            message (str): Optional custom message
        """
        user_info = LoggerHelper.get_user_info(request)
        request_info = LoggerHelper.get_request_info(request)
        logger.info(
            f"{message} | Status: {status_code} | {user_info} | {request_info}")

    @staticmethod
    def log_exception(logger, request, exception, message="Exception occurred"):
        """
        Log an exception with standardized format.

        Args:
            logger (logging.Logger): The logger instance
            request: The Django request object
            exception (Exception): The exception that occurred
            message (str): Optional custom message
        """
        user_info = LoggerHelper.get_user_info(request)
        request_info = LoggerHelper.get_request_info(request)
        logger.error(
            f"{message} | {user_info} | {request_info} | Exception: {str(exception)}",
            exc_info=True
        )
