import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

import app.services.profile as profile_module
from app.services.profile import ProfileService
from app.schemas.profile import ProfileUpdate


def _make_service() -> ProfileService:
    svc = ProfileService.__new__(ProfileService)
    svc._repo = AsyncMock()
    svc._follow_repo = AsyncMock()
    svc._s3 = AsyncMock()
    return svc


def _mock_profile(user_id: uuid.UUID | None = None) -> MagicMock:
    p = MagicMock()
    p.user_id = user_id or uuid.uuid4()
    p.username = "testuser"
    p.bio = None
    p.avatar_url = None
    p.social_links = {}
    return p


class TestGetProfileByUsername:
    async def test_not_found_raises_404(self):
        svc = _make_service()
        svc._repo.get_by_username.return_value = None
        with pytest.raises(HTTPException) as exc:
            await svc.get_profile_by_username("nobody")
        assert exc.value.status_code == 404


class TestBuildProfileDict:
    async def test_no_viewer_skips_is_following(self):
        svc = _make_service()
        profile = _mock_profile()
        svc._follow_repo.get_counts.return_value = (0, 0)

        await svc._build_profile_dict(profile, viewer_id=None)

        svc._follow_repo.is_following.assert_not_called()

    async def test_own_profile_skips_is_following(self):
        svc = _make_service()
        profile = _mock_profile()
        svc._follow_repo.get_counts.return_value = (0, 0)

        await svc._build_profile_dict(profile, viewer_id=profile.user_id)

        svc._follow_repo.is_following.assert_not_called()

    async def test_other_viewer_calls_is_following(self):
        svc = _make_service()
        profile = _mock_profile()
        viewer_id = uuid.uuid4()
        svc._follow_repo.get_counts.return_value = (5, 3)
        svc._follow_repo.is_following.return_value = True

        result = await svc._build_profile_dict(profile, viewer_id=viewer_id)

        svc._follow_repo.is_following.assert_called_once_with(viewer_id, profile.user_id)
        assert result["is_following"] is True

    async def test_returns_correct_counts(self):
        svc = _make_service()
        profile = _mock_profile()
        svc._follow_repo.get_counts.return_value = (12, 7)

        result = await svc._build_profile_dict(profile, viewer_id=None)

        assert result["followers_count"] == 12
        assert result["following_count"] == 7


class TestGetMyProfile:
    async def test_not_found_raises_404(self):
        svc = _make_service()
        svc._repo.get_by_user_id.return_value = None
        with pytest.raises(HTTPException) as exc:
            await svc.get_my_profile(uuid.uuid4())
        assert exc.value.status_code == 404


class TestUpdateMyProfile:
    async def test_profile_not_found_raises_404(self):
        svc = _make_service()
        svc._repo.get_by_user_id.return_value = None
        with pytest.raises(HTTPException) as exc:
            await svc.update_my_profile(uuid.uuid4(), ProfileUpdate())
        assert exc.value.status_code == 404

    async def test_empty_update_skips_repo_write(self, monkeypatch):
        svc = _make_service()
        user_id = uuid.uuid4()
        svc._repo.get_by_user_id.return_value = _mock_profile(user_id)
        monkeypatch.setattr(svc, "get_my_profile", AsyncMock(return_value={}))

        await svc.update_my_profile(user_id, ProfileUpdate())

        svc._repo.update_profile.assert_not_called()

    async def test_username_taken_raises_409(self):
        svc = _make_service()
        user_id = uuid.uuid4()
        profile = _mock_profile(user_id)
        profile.username = "old_name"
        svc._repo.get_by_user_id.return_value = profile
        svc._repo.is_username_available.return_value = False

        with pytest.raises(HTTPException) as exc:
            await svc.update_my_profile(user_id, ProfileUpdate(username="taken"))
        assert exc.value.status_code == 409

    async def test_same_username_skips_availability_check(self, monkeypatch):
        svc = _make_service()
        user_id = uuid.uuid4()
        profile = _mock_profile(user_id)
        profile.username = "myname"
        svc._repo.get_by_user_id.return_value = profile
        monkeypatch.setattr(svc, "get_my_profile", AsyncMock(return_value={}))

        # updating to the same username — availability check should be skipped
        await svc.update_my_profile(user_id, ProfileUpdate(username="myname"))

        svc._repo.is_username_available.assert_not_called()


class TestUploadAvatar:
    async def test_invalid_content_type_raises_400(self):
        svc = _make_service()
        file = AsyncMock()
        file.content_type = "application/pdf"
        with pytest.raises(HTTPException) as exc:
            await svc.upload_avatar(uuid.uuid4(), file)
        assert exc.value.status_code == 400

    async def test_file_too_large_raises_413(self, monkeypatch):
        svc = _make_service()
        file = AsyncMock()
        file.content_type = "image/jpeg"
        file.read.return_value = b"x" * 20
        monkeypatch.setattr(profile_module, "MAX_AVATAR_BYTES", 10)

        with pytest.raises(HTTPException) as exc:
            await svc.upload_avatar(uuid.uuid4(), file)
        assert exc.value.status_code == 413

    async def test_profile_not_found_raises_404(self):
        svc = _make_service()
        file = AsyncMock()
        file.content_type = "image/png"
        file.read.return_value = b"x" * 100
        svc._repo.get_by_user_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await svc.upload_avatar(uuid.uuid4(), file)
        assert exc.value.status_code == 404

    async def test_success_returns_presigned_url(self):
        svc = _make_service()
        user_id = uuid.uuid4()
        file = AsyncMock()
        file.content_type = "image/webp"
        file.read.return_value = b"x" * 100
        profile = _mock_profile(user_id)
        profile.avatar_url = None
        svc._repo.get_by_user_id.return_value = profile
        svc._s3.generate_presigned_url.return_value = "https://s3.example.com/avatars/avatar.webp"

        result = await svc.upload_avatar(user_id, file)

        svc._s3.upload_file.assert_called_once()
        svc._repo.update_profile.assert_called_once()
        assert result == "https://s3.example.com/avatars/avatar.webp"