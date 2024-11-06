# lolo/tournament/tests/test_api.py
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from ..models import Tournament, Category, VideoSubmission, Participation, Vote

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user():
    return User.objects.create_user(
        username='testuser',
        password='testpass123',
        email='test@example.com'
    )

@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        username='admin',
        password='admin123',
        email='admin@example.com'
    )

@pytest.fixture
def category():
    return Category.objects.create(
        name='Gaming',
        description='Gaming tournaments'
    )

@pytest.fixture
def tournament(category, admin_user):
    return Tournament.objects.create(
        title='Test Tournament',
        description='Test Description',
        category=category,
        created_by=admin_user,
        start_time='2024-10-28T00:00:00Z',
        end_time='2024-11-28T00:00:00Z'
    )

@pytest.mark.django_db
class TestCategoryAPI:
    def test_list_categories(self, api_client):
        """Test that anyone can list categories"""
        url = reverse('api:category-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_create_category_as_admin(self, api_client, admin_user):
        """Test that admin can create categories"""
        api_client.force_authenticate(user=admin_user)
        url = reverse('api:category-list')
        data = {
            'name': 'Music',
            'description': 'Music tournaments'
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Music'

    def test_create_category_as_normal_user(self, api_client, user):
        """Test that normal users cannot create categories"""
        api_client.force_authenticate(user=user)
        url = reverse('api:category-list')
        data = {
            'name': 'Music',
            'description': 'Music tournaments'
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
class TestTournamentAPI:
    def test_list_tournaments(self, api_client):
        """Test that anyone can list tournaments"""
        url = reverse('api:tournament-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_create_tournament_as_admin(self, api_client, admin_user, category):
        """Test that admin can create tournaments"""
        api_client.force_authenticate(user=admin_user)
        url = reverse('api:tournament-list')
        data = {
            'title': 'New Tournament',
            'description': 'Test tournament',
            'category': category.id,
            'start_time': '2024-10-28T00:00:00Z',
            'end_time': '2024-11-28T00:00:00Z'
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'New Tournament'

    def test_enter_tournament(self, api_client, user, tournament):
        """Test tournament entry"""
        api_client.force_authenticate(user=user)
        url = reverse('api:tournament-enter-tournament', kwargs={'pk': tournament.pk})
        
        # Simulate file upload
        with open('test_video.mp4', 'rb') as video_file:
            data = {
                'title': 'My Entry',
                'description': 'My tournament entry',
                'video_file': video_file,
            }
            response = api_client.post(url, data, format='multipart')
            assert response.status_code == status.HTTP_201_CREATED

    def test_vote_in_tournament(self, api_client, user, tournament):
        """Test voting in tournament"""
        api_client.force_authenticate(user=user)
        # Create a participation first
        participation = Participation.objects.create(
            user=user,
            tournament=tournament,
            video_submission=VideoSubmission.objects.create(
                title='Test Video',
                user=user
            )
        )

        url = reverse('api:tournament-vote', kwargs={'pk': tournament.pk})
        data = {'participation_id': participation.id}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED

@pytest.mark.django_db
class TestVideoSubmissionAPI:
    def test_user_can_upload_video(self, api_client, user):
        """Test that user can upload a video"""
        api_client.force_authenticate(user=user)
        url = reverse('api:videosubmission-list')
        
        with open('test_video.mp4', 'rb') as video_file:
            data = {
                'title': 'My Video',
                'description': 'Test video',
                'video_file': video_file,
            }
            response = api_client.post(url, data, format='multipart')
            assert response.status_code == status.HTTP_201_CREATED

    def test_user_can_only_delete_own_video(self, api_client, user):
        """Test that users can only delete their own videos"""
        other_user = User.objects.create_user(
            username='other',
            password='pass123'
        )
        video = VideoSubmission.objects.create(
            title='Test Video',
            user=other_user
        )
        
        api_client.force_authenticate(user=user)
        url = reverse('api:videosubmission-detail', kwargs={'pk': video.pk})
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDENpytest 