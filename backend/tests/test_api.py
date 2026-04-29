"""
Backend API Tests for VideoAI Studio
Tests: Health check, voices, projects CRUD, lip sync, face swap
"""
import pytest
import requests
import os
import time
from pathlib import Path

# Get backend URL from environment
BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    pytest.skip("EXPO_PUBLIC_BACKEND_URL not set", allow_module_level=True)

class TestHealthAndBasics:
    """Basic health and configuration tests"""
    
    def test_health_check(self):
        """Test GET /api/ returns version 4.0.0"""
        response = requests.get(f"{BASE_URL}/api/", timeout=10)
        assert response.status_code == 200, f"Health check failed with status {response.status_code}"
        
        data = response.json()
        assert "version" in data, "Response missing 'version' field"
        assert data["version"] == "4.0.0", f"Expected version 4.0.0, got {data['version']}"
        print(f"✓ Health check passed: {data}")
    
    def test_get_voices(self):
        """Test GET /api/voices returns Hindi and English voices"""
        response = requests.get(f"{BASE_URL}/api/voices", timeout=10)
        assert response.status_code == 200, f"Get voices failed with status {response.status_code}"
        
        data = response.json()
        assert "voices" in data, "Response missing 'voices' field"
        
        voices = data["voices"]
        assert len(voices) > 0, "No voices returned"
        
        # Check for Hindi voices
        hindi_voices = [v for v in voices if v.get("language") == "Hindi"]
        assert len(hindi_voices) >= 2, f"Expected at least 2 Hindi voices, got {len(hindi_voices)}"
        
        # Check for specific Hindi voices
        voice_ids = [v["id"] for v in voices]
        assert "hi-IN-SwaraNeural" in voice_ids, "Swara voice not found"
        assert "hi-IN-MadhurNeural" in voice_ids, "Madhur voice not found"
        
        # Check for English voices
        english_voices = [v for v in voices if "English" in v.get("language", "")]
        assert len(english_voices) > 0, "No English voices found"
        
        print(f"✓ Voices test passed: {len(voices)} voices, {len(hindi_voices)} Hindi, {len(english_voices)} English")
    
    def test_get_sound_effects(self):
        """Test GET /api/sound-effects returns sound effects list (v4 feature)"""
        response = requests.get(f"{BASE_URL}/api/sound-effects", timeout=10)
        assert response.status_code == 200, f"Get sound effects failed with status {response.status_code}"
        
        data = response.json()
        assert "effects" in data, "Response missing 'effects' field"
        
        effects = data["effects"]
        assert len(effects) > 0, "No sound effects returned"
        
        # Check for specific sound effects
        effect_ids = [e["id"] for e in effects]
        assert "none" in effect_ids, "None effect not found"
        assert "applause" in effect_ids, "Applause effect not found"
        assert "laugh" in effect_ids, "Laugh effect not found"
        assert "dramatic" in effect_ids, "Dramatic effect not found"
        assert "whoosh" in effect_ids, "Whoosh effect not found"
        
        # Verify structure
        for effect in effects:
            assert "id" in effect, "Effect missing 'id'"
            assert "name" in effect, "Effect missing 'name'"
            assert "icon" in effect, "Effect missing 'icon'"
        
        print(f"✓ Sound effects test passed: {len(effects)} effects found")


class TestProjects:
    """Project management tests"""
    
    def test_get_projects_empty_or_list(self):
        """Test GET /api/projects returns a list"""
        response = requests.get(f"{BASE_URL}/api/projects", timeout=10)
        assert response.status_code == 200, f"Get projects failed with status {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ Get projects passed: {len(data)} projects found")
    
    def test_get_nonexistent_project(self):
        """Test GET /api/project/{id} with invalid ID returns 404"""
        response = requests.get(f"{BASE_URL}/api/project/nonexistent-id-12345", timeout=10)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Nonexistent project returns 404")


class TestImageUpload:
    """Image upload tests"""
    
    def test_upload_image_without_file(self):
        """Test POST /api/upload-image without file returns 422"""
        response = requests.post(f"{BASE_URL}/api/upload-image", timeout=10)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Upload without file returns 422")
    
    def test_upload_face_image_without_file(self):
        """Test POST /api/upload-face-image without file returns 422"""
        response = requests.post(f"{BASE_URL}/api/upload-face-image", timeout=10)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Upload face image without file returns 422")


class TestVideoUpload:
    """Video upload tests - UPDATED FOR v4 (duration field)"""
    
    def test_upload_video_without_file(self):
        """Test POST /api/upload-video without file returns 422"""
        response = requests.post(f"{BASE_URL}/api/upload-video", timeout=10)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Upload video without file returns 422")
    
    def test_upload_video_with_non_video_file(self):
        """Test POST /api/upload-video with non-video file returns 400"""
        # Create a fake text file
        files = {'file': ('test.txt', b'not a video', 'text/plain')}
        response = requests.post(f"{BASE_URL}/api/upload-video", files=files, timeout=15)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Upload non-video file returns 400")
    
    def test_upload_video_response_includes_duration(self):
        """Test POST /api/upload-video response includes duration field (v4 feature)"""
        # Note: This test will fail without actual video file, but we can verify the endpoint structure
        # by checking error response or using a mock video file
        print("✓ Upload video duration field test (requires actual video file - skipped in unit tests)")
        pytest.skip("Requires actual video file upload")


class TestVideoDownload:
    """Video download proxy tests - NEW FEATURE"""
    
    def test_download_video_without_url(self):
        """Test GET /api/download-video without url parameter returns 422"""
        response = requests.get(f"{BASE_URL}/api/download-video", timeout=10)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Download video without url returns 422")
    
    def test_download_video_with_invalid_url(self):
        """Test GET /api/download-video with invalid url returns 502"""
        response = requests.get(f"{BASE_URL}/api/download-video?url=https://invalid-url-12345.com/video.mp4", timeout=15)
        assert response.status_code in [502, 500], f"Expected 502 or 500, got {response.status_code}"
        print("✓ Download video with invalid url returns error")


class TestLipSyncCreation:
    """Lip sync video creation tests - UPDATED FOR v4 (multi-character)"""
    
    def test_create_lipsync_multi_character(self):
        """Test POST /api/create-lipsync with multi-character (v4 feature)"""
        payload = {
            "image_urls": [
                "https://example.com/character1.jpg",
                "https://example.com/character2.jpg"
            ],
            "dialogue_lines": [
                {"character_index": 0, "text": "Hello, I am character 1"},
                {"character_index": 1, "text": "And I am character 2"},
                {"character_index": 0, "text": "Nice to meet you!"}
            ],
            "voice_id": "hi-IN-SwaraNeural",
            "aspect_ratio": "16:9",
            "sound_effect": "applause"
        }
        
        response = requests.post(f"{BASE_URL}/api/create-lipsync", json=payload, timeout=15)
        assert response.status_code == 200, f"Create multi-character lipsync failed: {response.text}"
        
        data = response.json()
        assert "project_id" in data, "Response missing 'project_id'"
        assert "status" in data, "Response missing 'status'"
        assert data["status"] == "processing", f"Expected status 'processing', got {data['status']}"
        
        project_id = data["project_id"]
        print(f"✓ Multi-character lip sync creation passed: project_id={project_id}")
        
        # Verify project was created with correct face_count
        time.sleep(1)
        get_response = requests.get(f"{BASE_URL}/api/project/{project_id}", timeout=10)
        assert get_response.status_code == 200, "Failed to retrieve created project"
        
        project_data = get_response.json()
        assert project_data["type"] == "lipsync", f"Expected type 'lipsync', got {project_data['type']}"
        assert project_data["face_count"] == 2, f"Expected face_count 2, got {project_data.get('face_count')}"
        assert project_data["sound_effect"] == "applause", f"Expected sound_effect 'applause', got {project_data.get('sound_effect')}"
        print(f"✓ Multi-character project verified: 2 characters, 3 dialogue lines, applause sound effect")
        
        return project_id
    
    def test_create_lipsync_single_character_new_api(self):
        """Test POST /api/create-lipsync with single character using new API model"""
        payload = {
            "image_urls": ["https://example.com/single-char.jpg"],
            "dialogue_lines": [
                {"character_index": 0, "text": "This is a single character speaking."}
            ],
            "voice_id": "en-US-JennyNeural",
            "aspect_ratio": "9:16"
        }
        
        response = requests.post(f"{BASE_URL}/api/create-lipsync", json=payload, timeout=15)
        assert response.status_code == 200, f"Create single-character lipsync failed: {response.text}"
        
        data = response.json()
        project_id = data["project_id"]
        
        # Verify single character
        time.sleep(1)
        get_response = requests.get(f"{BASE_URL}/api/project/{project_id}", timeout=10)
        project_data = get_response.json()
        assert project_data["face_count"] == 1, f"Expected face_count 1, got {project_data.get('face_count')}"
        print(f"✓ Single character lip sync test passed (new API)")
    
    def test_create_lipsync_with_sound_effect(self):
        """Test POST /api/create-lipsync with sound effect (v4 feature)"""
        payload = {
            "image_urls": ["https://example.com/test.jpg"],
            "dialogue_lines": [{"character_index": 0, "text": "Testing sound effects"}],
            "voice_id": "hi-IN-MadhurNeural",
            "sound_effect": "dramatic"
        }
        
        response = requests.post(f"{BASE_URL}/api/create-lipsync", json=payload, timeout=15)
        assert response.status_code == 200, f"Create lipsync with sound effect failed: {response.text}"
        
        data = response.json()
        project_id = data["project_id"]
        
        # Verify sound effect stored
        time.sleep(1)
        get_response = requests.get(f"{BASE_URL}/api/project/{project_id}", timeout=10)
        project_data = get_response.json()
        assert project_data["sound_effect"] == "dramatic", f"Expected sound_effect 'dramatic', got {project_data.get('sound_effect')}"
        print(f"✓ Sound effect test passed")
    
    def test_create_lipsync_missing_image_urls(self):
        """Test POST /api/create-lipsync without image_urls returns 422"""
        payload = {
            "dialogue_lines": [{"character_index": 0, "text": "Test"}],
            "voice_id": "en-US-JennyNeural"
        }
        
        response = requests.post(f"{BASE_URL}/api/create-lipsync", json=payload, timeout=10)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Missing image_urls returns 422")
    
    def test_create_lipsync_missing_dialogue_lines(self):
        """Test POST /api/create-lipsync without dialogue_lines returns 422"""
        payload = {
            "image_urls": ["https://example.com/test.jpg"],
            "voice_id": "en-US-JennyNeural"
        }
        
        response = requests.post(f"{BASE_URL}/api/create-lipsync", json=payload, timeout=10)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Missing dialogue_lines returns 422")


class TestFaceSwapCreation:
    """Face swap video creation tests - UPDATED FOR v4 (video trimming)"""
    
    def test_create_faceswap_with_single_face(self):
        """Test POST /api/create-faceswap with single face"""
        payload = {
            "source_image_paths": ["/tmp/test-face.jpg"],
            "target_video_path": "https://example.com/test-video.mp4",
            "aspect_ratio": "16:9"
        }
        
        response = requests.post(f"{BASE_URL}/api/create-faceswap", json=payload, timeout=15)
        assert response.status_code == 200, f"Create faceswap failed with status {response.status_code}: {response.text}"
        
        data = response.json()
        assert "project_id" in data, "Response missing 'project_id'"
        assert "status" in data, "Response missing 'status'"
        assert data["status"] == "processing", f"Expected status 'processing', got {data['status']}"
        
        project_id = data["project_id"]
        print(f"✓ Face swap creation (single face) passed: project_id={project_id}")
        
        # Verify project was created
        time.sleep(1)
        get_response = requests.get(f"{BASE_URL}/api/project/{project_id}", timeout=10)
        assert get_response.status_code == 200, "Failed to retrieve created project"
        
        project_data = get_response.json()
        assert project_data["type"] == "faceswap", f"Expected type 'faceswap', got {project_data['type']}"
        assert project_data["aspect_ratio"] == "16:9", f"Expected aspect_ratio '16:9', got {project_data.get('aspect_ratio')}"
        assert project_data["face_count"] == 1, f"Expected face_count 1, got {project_data.get('face_count')}"
        print(f"✓ Face swap project persistence verified (1 face)")
        
        return project_id
    
    def test_create_faceswap_with_video_trimming(self):
        """Test POST /api/create-faceswap with trim_start and trim_end (v4 feature)"""
        payload = {
            "source_image_paths": ["/tmp/face.jpg"],
            "target_video_path": "https://example.com/video.mp4",
            "aspect_ratio": "16:9",
            "trim_start": 5.0,
            "trim_end": 15.0
        }
        
        response = requests.post(f"{BASE_URL}/api/create-faceswap", json=payload, timeout=15)
        assert response.status_code == 200, f"Create faceswap with trimming failed: {response.text}"
        
        data = response.json()
        project_id = data["project_id"]
        print(f"✓ Face swap with video trimming passed: project_id={project_id}")
        
        # Verify trim parameters stored
        time.sleep(1)
        get_response = requests.get(f"{BASE_URL}/api/project/{project_id}", timeout=10)
        project_data = get_response.json()
        assert project_data["trim_start"] == 5.0, f"Expected trim_start 5.0, got {project_data.get('trim_start')}"
        assert project_data["trim_end"] == 15.0, f"Expected trim_end 15.0, got {project_data.get('trim_end')}"
        print(f"✓ Video trim parameters verified: 5.0s to 15.0s")
    
    def test_create_faceswap_with_multiple_faces(self):
        """Test POST /api/create-faceswap with multiple faces"""
        payload = {
            "source_image_paths": ["/tmp/face1.jpg", "/tmp/face2.jpg", "/tmp/face3.jpg"],
            "target_video_path": "https://example.com/multi-person-video.mp4",
            "aspect_ratio": "9:16"
        }
        
        response = requests.post(f"{BASE_URL}/api/create-faceswap", json=payload, timeout=15)
        assert response.status_code == 200, f"Create multi-face swap failed: {response.text}"
        
        data = response.json()
        project_id = data["project_id"]
        print(f"✓ Multi-face swap creation passed: project_id={project_id}")
        
        # Verify face count
        time.sleep(1)
        get_response = requests.get(f"{BASE_URL}/api/project/{project_id}", timeout=10)
        project_data = get_response.json()
        assert project_data["face_count"] == 3, f"Expected face_count 3, got {project_data.get('face_count')}"
        print(f"✓ Multi-face swap project verified (3 faces)")
    
    def test_create_faceswap_with_trimming_and_multiple_faces(self):
        """Test POST /api/create-faceswap with both trimming and multiple faces (v4 combined)"""
        payload = {
            "source_image_paths": ["/tmp/face1.jpg", "/tmp/face2.jpg"],
            "target_video_path": "https://example.com/video.mp4",
            "aspect_ratio": "16:9",
            "trim_start": 2.5,
            "trim_end": 10.0
        }
        
        response = requests.post(f"{BASE_URL}/api/create-faceswap", json=payload, timeout=15)
        assert response.status_code == 200, f"Create faceswap with trimming and multi-face failed: {response.text}"
        
        data = response.json()
        project_id = data["project_id"]
        
        # Verify both features
        time.sleep(1)
        get_response = requests.get(f"{BASE_URL}/api/project/{project_id}", timeout=10)
        project_data = get_response.json()
        assert project_data["face_count"] == 2, f"Expected face_count 2, got {project_data.get('face_count')}"
        assert project_data["trim_start"] == 2.5, f"Expected trim_start 2.5, got {project_data.get('trim_start')}"
        assert project_data["trim_end"] == 10.0, f"Expected trim_end 10.0, got {project_data.get('trim_end')}"
        print(f"✓ Combined test passed: 2 faces + trimming (2.5s to 10.0s)")
    
    def test_create_faceswap_missing_source_images(self):
        """Test POST /api/create-faceswap without source_image_paths returns 422"""
        payload = {
            "target_video_path": "https://example.com/video.mp4"
        }
        
        response = requests.post(f"{BASE_URL}/api/create-faceswap", json=payload, timeout=10)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Missing source_image_paths returns 422")
    
    def test_create_faceswap_missing_target_video(self):
        """Test POST /api/create-faceswap without target_video_path returns 422"""
        payload = {
            "source_image_paths": ["/tmp/face.jpg"]
        }
        
        response = requests.post(f"{BASE_URL}/api/create-faceswap", json=payload, timeout=10)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Missing target_video_path returns 422")
    
    def test_create_faceswap_empty_source_images(self):
        """Test POST /api/create-faceswap with empty source_image_paths array"""
        payload = {
            "source_image_paths": [],
            "target_video_path": "https://example.com/video.mp4"
        }
        
        response = requests.post(f"{BASE_URL}/api/create-faceswap", json=payload, timeout=10)
        # Should either return 422 or 200 (backend will handle empty array)
        assert response.status_code in [200, 422], f"Unexpected status {response.status_code}"
        print("✓ Empty source_image_paths handled")


class TestProjectDeletion:
    """Project deletion tests"""
    
    def test_delete_project(self):
        """Test DELETE /api/project/{id}"""
        # First create a project using new v4 API
        payload = {
            "image_urls": ["https://example.com/delete-test.jpg"],
            "dialogue_lines": [{"character_index": 0, "text": "This project will be deleted"}],
            "voice_id": "en-US-GuyNeural"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/create-lipsync", json=payload, timeout=15)
        assert create_response.status_code == 200
        project_id = create_response.json()["project_id"]
        
        # Delete the project
        delete_response = requests.delete(f"{BASE_URL}/api/project/{project_id}", timeout=10)
        assert delete_response.status_code == 200, f"Delete failed with status {delete_response.status_code}"
        
        # Verify deletion
        get_response = requests.get(f"{BASE_URL}/api/project/{project_id}", timeout=10)
        assert get_response.status_code == 404, "Project still exists after deletion"
        print(f"✓ Project deletion test passed")
    
    def test_delete_nonexistent_project(self):
        """Test DELETE /api/project/{id} with invalid ID returns 404"""
        response = requests.delete(f"{BASE_URL}/api/project/nonexistent-delete-id", timeout=10)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Delete nonexistent project returns 404")
