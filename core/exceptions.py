from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return response

    error_data = response.data

    if isinstance(error_data, dict) and "detail" in error_data:
        message = str(error_data["detail"])
        details = None
    else:
        message = "Validation error."
        details = error_data

    response.data = {
        "success": False,
        "error": {
            "code": get_error_code(response.status_code),
            "message": message,
            "details": details,
        },
    }

    return response


def get_error_code(status_code):
    error_codes = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
    }

    return error_codes.get(
        status_code,
        "API_ERROR",
    )