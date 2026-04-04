from fastapi import Request


def get_services(request: Request):
    return request.app.state.services
