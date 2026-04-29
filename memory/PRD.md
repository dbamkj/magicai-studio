# VideoAI Studio - Product Requirements Document

## Overview
VideoAI Studio is a production-ready mobile application for creating AI-powered videos with lip sync and face swap capabilities, similar to KlingAI and WANAi.

## Core Features

### 1. Lip Sync (Implemented)
- **Description**: Create talking avatar videos by syncing lips with audio or text
- **Functionality**:
  - Upload images from gallery or capture with camera
  - Enter text script (up to 5000 characters)
  - Select voice (Jenny/Guy)
  - AI-powered lip synchronization using D-ID API
  - Support for videos up to 5 minutes long
  - Support for 16:9 and 9:16 aspect ratios

### 2. Face Swap (Planned)
- **Description**: Replace faces in videos with AI
- **Status**: Coming soon (placeholder screen implemented)
- **Planned Features**:
  - Seamless face replacement
  - Real-time processing
  - Automatic color matching
  - Advanced face detection

### 3. My Projects
- **Description**: View and manage all created videos
- **Functionality**:
  - List all projects
  - View project status (created, processing, completed, failed)
  - Refresh to check updates
  - View completed video URLs
  - Track generation progress

## Technical Stack

### Frontend
- **Framework**: Expo (React Native)
- **Navigation**: Expo Router (file-based routing)
- **UI**: React Native components with custom styling
- **Image Handling**: expo-image-picker, expo-camera
- **HTTP Client**: axios
- **Icons**: @expo/vector-icons (Ionicons)

### Backend
- **Framework**: FastAPI (Python)
- **Database**: MongoDB
- **AI Service**: D-ID API
- **Image Processing**: Pillow
- **HTTP Client**: httpx

### AI Integration
- **Service**: D-ID API
- **Capabilities**:
  - Image upload to D-ID storage
  - Talking head video generation
  - Text-to-speech with multiple voices
  - Audio-based lip sync (future)
  - Background processing with status polling

## API Endpoints

### Backend Endpoints
- `GET /api/` - Health check
- `POST /api/upload-image` - Upload image to D-ID
- `POST /api/upload-audio` - Upload audio (placeholder)
- `POST /api/create-lipsync` - Create lip sync video
- `GET /api/project/{project_id}` - Get project details
- `GET /api/projects` - List all projects

## User Flow

### Lip Sync Creation
1. User opens app → Home screen
2. Taps "Lip Sync" card
3. Selects image from gallery or takes photo
4. Image uploads to D-ID automatically
5. User enters script text
6. Selects voice (Jenny or Guy)
7. Taps "Create Lip Sync Video"
8. Video generation starts in background
9. User can view progress in "My Projects"
10. When complete, user can access video URL

### Project Management
1. User taps "My Projects"
2. Views list of all projects with status
3. Taps a project to see details
4. For completed projects, views video URL
5. Can refresh to check for updates

## Video Specifications

### Supported Features
- **Max Video Length**: 5 minutes (300 seconds)
- **Aspect Ratios**: 
  - 16:9 (landscape - 1280x720)
  - 9:16 (portrait - 720x1280)
  - 1:1 (square - 1080x1080)
- **Image Formats**: JPEG, JPG, PNG
- **Max Image Size**: 10MB
- **Min Face Size**: 200x200 pixels

### Voice Options
- Jenny (en-US-JennyNeural) - Female voice
- Guy (en-US-GuyNeural) - Male voice

## Database Schema

### VideoProject Collection
```javascript
{
  id: string (UUID),
  name: string,
  type: "lipsync" | "faceswap",
  status: "created" | "processing" | "completed" | "failed",
  video_path: string (optional),
  image_url: string (optional),
  audio_url: string (optional),
  result_url: string (optional),
  d_id_talk_id: string (optional),
  created_at: datetime,
  updated_at: datetime,
  error_message: string (optional)
}
```

## Key Features Implementation Status

✅ **Completed**:
- Home screen with feature cards
- Lip sync video creation
- Image upload (gallery + camera)
- Text-to-speech integration
- Voice selection
- Background video processing
- Project management
- Status tracking
- Error handling
- Responsive mobile UI
- Permission handling
- D-ID API integration

🚧 **In Progress/Planned**:
- Face swap feature
- Audio file upload for lip sync
- Cloud storage for videos
- Video preview in app
- Download videos to device
- Share videos
- Advanced editing options
- Multiple aspect ratio selection UI
- Batch processing

## Security & Privacy
- API keys stored in environment variables
- Secure D-ID authentication using Basic Auth
- Temporary file cleanup after upload
- No sensitive data in logs

## Error Handling
- Image validation (size, format, dimensions)
- Upload error recovery
- API error messages
- User-friendly alerts
- Background task failure handling

## Performance Optimizations
- Exponential backoff for status polling
- Image compression for large files
- Async background processing
- Efficient MongoDB queries
- Connection pooling

## Future Enhancements
1. Face swap implementation
2. Video editing tools
3. Custom voice training
4. Batch video generation
5. Template library
6. Social media sharing
7. Video preview player
8. Local video storage
9. Export options (different formats)
10. Advanced motion control
