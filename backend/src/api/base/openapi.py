from fastapi import status

from src.api.base.schema import ResponseError


def openapi_response(
        response_model,
        success_status_code: int = status.HTTP_200_OK,
        success_description: str = None,
        success_examples: dict = None,
        fail_status_code: int = status.HTTP_400_BAD_REQUEST,
        fail_description: str = None,
        fail_examples: dict = None,
):
    status_code__details = {
        success_status_code: {
            'model': response_model
        },
        fail_status_code: {
            'model': ResponseError
        }
    }
    if success_description:
        status_code__details[success_status_code]['description'] = success_description
    if success_examples:
        status_code__details[success_status_code]['content'] = {
            'application/json': {
                'examples': success_examples
            }
        }

    if fail_description:
        status_code__details[fail_status_code]['description'] = fail_description
    if fail_examples:
        status_code__details[fail_status_code]['content'] = {
            'application/json': {
                'examples': fail_examples
            }
        }

    return status_code__details
