"""认证接口：注册 / 登录 / 当前用户 / 退出说明。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import AuthService, CurrentUser, get_auth_service
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter()


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="注册新用户",
    responses={409: {"description": "用户名已被占用"}},
)
def register(
    data: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> UserOut:
    """创建用户；成功后请调用登录接口获取令牌。"""
    user = service.register(data.username, data.password)
    return UserOut.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="登录并获取访问令牌",
    responses={401: {"description": "用户名或密码错误"}},
)
def login(
    data: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """校验用户名密码，签发 JWT 访问令牌。"""
    user, token = service.login(data.username, data.password)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut, summary="获取当前登录用户")
def me(user: CurrentUser) -> UserOut:
    """携带 Bearer 令牌访问，返回当前用户信息。"""
    return UserOut.model_validate(user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="退出登录（客户端删除令牌）",
)
def logout(user: CurrentUser) -> None:
    """本系统使用无状态 JWT：退出由客户端删除令牌完成，服务端返回 204 确认。"""
    return None
