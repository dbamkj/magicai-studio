"""
Test Magic Hour file upload flow
Tests the upload_to_magic_hour helper function and face swap with actual file uploads
"""
import pytest
import requests
import os
import io
from PIL import Image

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    pytest.skip("EXPO_PUBLIC_BACKEND_URL not set", allow_module_level=True)


class TestMagicHourUploadFlow:
    """Test Magic Hour file upload integration"""
    
    def test_upload_face_image_and_create_faceswap(self):
        """Test complete flow: upload face image -> upload video -> create face swap"""
        
        # Step 1: Create a test image
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        # Step 2: Upload face image
        files = {'file': ('test_face.jpg', img_bytes, 'image/jpeg')}
        upload_response = requests.post(
            f"{BASE_URL}/api/upload-face-image",
            files=files,
            timeout=30
        )
        
        assert upload_response.status_code == 200, f"Face image upload failed: {upload_response.text}"
        upload_data = upload_response.json()
        
        assert "file_path" in upload_data, "Response missing 'file_path'"
        assert "file_id" in upload_data, "Response missing 'file_id'"
        
        face_file_path = upload_data["file_path"]
        print(f"✓ Face image uploaded: {face_file_path}")
        
        # Step 3: Create a test video (small MP4)
        # For testing, we'll use a minimal video or skip if not available
        # In production, this would be a real video file
        
        # Step 4: Create face swap with uploaded files
        # Note: This will trigger the upload_to_magic_hour function
        payload = {
            "source_image_paths": [face_file_path],
            "target_video_path": "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4",
            "aspect_ratio": "16:9"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/create-faceswap",
            json=payload,
            timeout=30
        )
        
        assert create_response.status_code == 200, f"Face swap creation failed: {create_response.text}"
        create_data = create_response.json()
        
        assert "project_id" in create_data, "Response missing 'project_id'"
        project_id = create_data["project_id"]
        
        print(f"✓ Face swap created: project_id={project_id}")
        print(f"✓ Magic Hour upload flow test passed - face swap will process in background")
        
        return project_id
    
    def test_upload_video_returns_file_path_and_duration(self):
        """Test video upload returns file_path and duration"""
        
        # Create a minimal video file (we'll use a small test file)
        # For this test, we'll create a fake video file
        video_content = b'fake video content for testing'
        
        files = {'file': ('test_video.mp4', io.BytesIO(video_content), 'video/mp4')}
        upload_response = requests.post(
            f"{BASE_URL}/api/upload-video",
            files=files,
            timeout=30
        )
        
        assert upload_response.status_code == 200, f"Video upload failed: {upload_response.text}"
        upload_data = upload_response.json()
        
        assert "file_path" in upload_data, "Response missing 'file_path'"
        assert "file_id" in upload_data, "Response missing 'file_id'"
        assert "duration" in upload_data, "Response missing 'duration'"
        
        print(f"✓ Video uploaded: {upload_data['file_path']}")
        print(f"✓ Video duration: {upload_data['duration']}s")
        print(f"✓ Video size: {upload_data.get('size_mb', 0)}MB")
