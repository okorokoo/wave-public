import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.services.profile import FollowService
from app.schemas.profile import FollowToggleResponse


def _make_service() -> FollowService:
    svc = FollowService.__new__(FollowService)
    svc._repo = AsyncMock()
    svc._profile_repo = AsyncMock()
    return svc


class TestFollowToggle:
    async def test_self_follow_raises_400(self):
        svc = _make_service()
        user_id = uuid.uuid4()
        with pytest.raises(HTTPException) as exc:
            await svc.toggle(user_id, user_id)
        assert exc.value.status_code == 400

    async def test_target_not_found_raises_404(self):
        svc = _make_service()
        svc._profile_repo.get_by_user_id.return_value = None
        with pytest.raises(HTTPException) as exc:
            await svc.toggle(uuid.uuid4(), uuid.uuid4())
        assert exc.value.status_code == 404

    async def test_follow_success_returns_response(self):
        svc = _make_service()
        svc._profile_repo.get_by_user_id.return_value = MagicMock()
        svc._repo.toggle.return_value = (True, 7)
        result = await svc.toggle(uuid.uuid4(), uuid.uuid4())
        assert isinstance(result, FollowToggleResponse)
        assert result.is_following is True
        assert result.followers_count == 7

    async def test_unfollow_success_returns_false(self):
        svc = _make_service()
        svc._profile_repo.get_by_user_id.return_value = MagicMock()
        svc._repo.toggle.return_value = (False, 3)
        result = await svc.toggle(uuid.uuid4(), uuid.uuid4())
        assert result.is_following is False
        assert result.followers_count == 3
