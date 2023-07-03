import secrets
from datetime import timedelta
from itertools import filterfalse
from typing import Optional

from api.config import crd

from asyncpg.pgproto.types import Point as PgPoint
from asyncpg.types import Range
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2AuthorizationCodeBearer
from keycloak import KeycloakOpenID
from sqlalchemy import func
from sqlalchemy.types import UserDefinedType

keycloak_openid = KeycloakOpenID(
    server_url=crd.oidc.KC_SERVER_URL,
    client_id=crd.oidc.KC_CLIENT_ID,
    realm_name=crd.oidc.KC_REALM_NAME,
    client_secret_key=crd.oidc.KC_CLIENT_SECRET,
)

crd.oidc.KC_PUBLIC_KEY = (
    '-----BEGIN PUBLIC KEY-----\n'
    + keycloak_openid.public_key()
    + '\n-----END PUBLIC KEY-----'
)

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f'{crd.oidc.KC_SERVER_URL}realms/{crd.oidc.KC_REALM_NAME}/protocol/openid-connect/auth',
    tokenUrl=f'{crd.oidc.KC_SERVER_URL}realms/{crd.oidc.KC_REALM_NAME}/protocol/openid-connect/token',
)

def get_user(token: str = Depends(oauth2_scheme)):
    try:
        auth = keycloak_openid.decode_token(
            token,
            key=crd.oidc.KC_PUBLIC_KEY,
            options={'verify_signature': True, 'verify_aud': False, 'exp': True},
        )
        return auth

    except:
        return None

class AuthenticationChecker:
    def __init__(self, required_roles: list = []) -> None:
        self.required_roles = required_roles
    def __call__(self, user:dict=Depends(get_user)) -> bool:
        for r_perm in self.required_roles:
            if r_perm not in user["realm_access"]["roles"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Permissions",
                )
        return True

async def check_oid_authentication(token: str = Depends(oauth2_scheme)):
    try:
        auth = keycloak_openid.decode_token(
            token,
            key=crd.oidc.KC_PUBLIC_KEY,
            options={'verify_signature': True, 'verify_aud': False, 'exp': True},
        )
        if 'internal' not in auth['realm_access']['roles']:
            raise
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Authentication failed',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    else:
        return auth

async def check_oid_m2m_authentication(role, token: str = Depends(oauth2_scheme)):
    try:
        auth = keycloak_openid.decode_token(
            token,
            key=crd.oidc.KC_PUBLIC_KEY,
            options={'verify_signature': True, 'verify_aud': False, 'exp': True},
        )
        if role == None or role not in auth['realm_access']['roles']:
            raise
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Authentication failed',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    else:
        return auth

security = HTTPBasic()

async def check_authentication(
    credentials: HTTPBasicCredentials = Depends(security),
    authorization: Optional[str] = Header(None)
    ):
    correct_username = secrets.compare_digest(credentials.username, crd.ba.username)
    correct_password = secrets.compare_digest(credentials.password, crd.ba.password)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect username or password',
            headers={'WWW-Authenticate': 'Basic'},
        )
    return { 'authenticated': True }

def unique_everseen(iterable, key=None):
    '''List unique elements, preserving order. Remember all elements ever seen.'''
    seen = set()
    seen_add = seen.add
    if key is None:
        for element in filterfalse(seen.__contains__, iterable):
            seen_add(element)
            yield element
    else:
        for element in iterable:
            k = key(element)
            if k not in seen:
                seen_add(k)
                yield element

def from_inclusive_range(period: Range) -> Range:
    return Range(period.lower, None if period.upper == None else period.upper - timedelta(days=1))

def to_inclusive_range(period: Range) -> Range:
    return Range(period.lower, None if period.upper == None else period.upper + timedelta(days=1))

class GeometryPoint(UserDefinedType):

    def get_col_spec(self):
        return "POINT"

    def bind_expression(self, bindvalue):
        return func.Point(bindvalue, type_=self)

    def column_expression(self, col):
        return col

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            assert isinstance(value, tuple)
            lat, lon = value
            return "POINT(%s, %s)" % (lat, lon)
        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            assert isinstance(value, PgPoint)
            return {'lat': float(value.x), 'lon': float(value.y)}
        return process

def aggregation_mapper(aggregation, column_name):
    mapping = {
        'mean': 'avg({}) as value',
        'sum': 'sum({}) as value',
        'min': 'min({}) as value',
        'max': 'max({}) as value',
        'median': "percentile_cont(0.5) WITHIN GROUP (ORDER BY {}) as value",
        'q1': "percentile_cont(0.25) WITHIN GROUP (ORDER BY {}) as value",
        'q3': "percentile_cont(0.75) WITHIN GROUP (ORDER BY {}) as value",
    }
    if not aggregation in mapping:
        return None
    return mapping[aggregation].format(column_name)

def pollinator_class_mapper(pollinator_class):
    mapping = {
        'fliege': 5564,
        'honigbiene': 1334757,
        'hummel': 1340278,
        'schwebfliege': 6920,
        'wildbiene': 4334,
    }
    if not pollinator_class in mapping:
        return None
    return mapping[pollinator_class]