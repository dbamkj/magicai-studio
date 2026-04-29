# VideoAI Studio 🎥

A production-ready mobile application for creating AI-powered videos with lip sync and face swap capabilities, similar to KlingAI and WANAi.

## 🌟 Features

### ✅ Implemented Features
- **Lip Sync Videos**: Create talking avatar videos by syncing lips with text
- **Image Upload**: Select from gallery or capture with camera
- **Text-to-Speech**: Multiple voice options (Jenny/Guy)
- **Project Management**: Track all your video projects
- **Background Processing**: Videos generate in the background
- **Status Tracking**: Monitor video generation progress
- **Mobile-First UI**: Beautiful, responsive interface for mobile devices

### 🚧 Coming Soon
- **Face Swap**: Replace faces in videos with AI
- **Audio Upload**: Use custom audio files for lip sync
- **Video Preview**: Watch videos directly in the app
- **Download**: Save videos to device storage

## 📱 Screenshots

**Home Screen** → **Lip Sync** → **My Projects**

## 🛠️ Tech Stack

### Frontend
- **Expo** (React Native) - Cross-platform mobile development
- **Expo Router** - File-based navigation
- **TypeScript** - Type-safe development
- **Axios** - HTTP client
- **Ionicons** - Beautiful icons

### Backend
- **FastAPI** - High-performance Python API
- **MongoDB** - Document database
- **D-ID API** - AI video generation
- **Pillow** - Image processing

## 🚀 Getting Started

### Prerequisites
- Node.js 18+
- Python 3.11+
- MongoDB
- D-ID API key

### Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd videoai-studio
```

2. **Backend Setup**
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your D-ID API key:
# D_ID_API_KEY=your_api_key_here

# Start backend
uvicorn server:app --reload --host 0.0.0.0 --port 8001
```

3. **Frontend Setup**
```bash
cd frontend

# Install dependencies
yarn install

# Start Expo
yarn start
```

4. **Access the App**
- Scan QR code with Expo Go app (iOS/Android)
- Or press `w` to open in web browser

## 🔑 D-ID API Key

### How to Get Your API Key

1. Visit [D-ID Studio](https://studio.d-id.com/)
2. Sign up or log in
3. Go to Account Settings
4. Generate API Key
5. Copy the key and add to `backend/.env`

### API Key Format
```env
D_ID_API_KEY=your_base64_email:your_api_token
```

## 📖 Usage

### Creating a Lip Sync Video

1. **Open the app** and tap "Lip Sync"
2. **Select an image**:
   - Tap "Gallery" to choose from photos
   - Or tap "Camera" to take a new photo
3. **Enter your script** (up to 5000 characters)
4. **Select a voice** (Jenny or Guy)
5. **Tap "Create Lip Sync Video"**
6. **View progress** in "My Projects"
7. **Access result** when status shows "Completed"

### Checking Project Status

1. Tap "My Projects" from home screen
2. View all projects with status indicators:
   - 🟢 **Completed**: Video is ready
   - 🟡 **Processing**: Video is being generated
   - 🔴 **Failed**: Generation failed
3. Tap any project to see details
4. Pull down to refresh

## 🎯 Video Specifications

| Feature | Specification |
|---------|--------------|
| **Max Video Length** | 5 minutes (300 seconds) |
| **Aspect Ratios** | 16:9, 9:16, 1:1 |
| **Image Formats** | JPEG, JPG, PNG |
| **Max Image Size** | 10 MB |
| **Min Face Size** | 200x200 pixels |

## 🏗️ Architecture

### File Structure
```
videoai-studio/
├── backend/
│   ├── server.py          # FastAPI application
│   ├── .env               # Environment variables
│   └── requirements.txt   # Python dependencies
│
├── frontend/
│   ├── app/
│   │   ├── index.tsx      # Home screen
│   │   ├── lipsync.tsx    # Lip sync feature
│   │   ├── faceswap.tsx   # Face swap (coming soon)
│   │   └── projects.tsx   # Project management
│   ├── app.json           # Expo configuration
│   └── package.json       # Node dependencies
│
└── memory/
    └── PRD.md             # Product requirements
```

### Data Flow

```
User Selects Image
    ↓
Image Uploaded to D-ID
    ↓
User Enters Script & Voice
    ↓
Backend Creates Talk Request
    ↓
D-ID Generates Video (Background)
    ↓
Backend Polls Status
    ↓
Video URL Saved to MongoDB
    ↓
User Views Result in Projects
```

## 🔐 Security

- API keys stored in environment variables
- Secure Basic Auth for D-ID API
- Temporary file cleanup after processing
- No sensitive data in logs
- MongoDB connection over localhost

## 🧪 Testing

### Backend Testing
```bash
# Test API endpoint
curl http://localhost:8001/api/

# Test image upload
curl -X POST http://localhost:8001/api/upload-image \
  -F "file=@test-image.jpg"

# Get projects
curl http://localhost:8001/api/projects
```

### Frontend Testing
- Use Expo Go app on physical device
- Test camera permissions
- Test gallery permissions
- Verify image upload
- Check project status updates

## 📊 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/` | Health check |
| POST | `/api/upload-image` | Upload image to D-ID |
| POST | `/api/create-lipsync` | Create lip sync video |
| GET | `/api/project/{id}` | Get project details |
| GET | `/api/projects` | List all projects |

## 🐛 Troubleshooting

### Common Issues

**Image upload fails**
- Check image size (max 10MB)
- Ensure valid format (JPEG, PNG)
- Verify D-ID API key is correct

**Video generation stuck**
- Check backend logs
- Verify D-ID API quota
- Check MongoDB connection

**App permissions denied**
- Go to device Settings
- Find VideoAI Studio
- Enable Camera and Photos permissions

## 🔄 Environment Variables

### Backend (.env)
```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=videoai_database
D_ID_API_KEY=your_d_id_api_key
D_ID_API_URL=https://api.d-id.com
```

### Frontend (.env)
```env
EXPO_PUBLIC_BACKEND_URL=http://localhost:8001
```

## 📈 Performance

- **Background Processing**: Videos generate without blocking UI
- **Exponential Backoff**: Smart polling to reduce API calls
- **Image Compression**: Automatic compression for large files
- **Connection Pooling**: Efficient database queries

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a pull request

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- **D-ID** for AI video generation API
- **Expo** for mobile development framework
- **FastAPI** for backend framework

## 📞 Support

For issues or questions:
- Open an issue on GitHub
- Check existing documentation
- Review D-ID API docs

## 🗺️ Roadmap

### Version 1.0 (Current)
- ✅ Lip sync video generation
- ✅ Image upload (camera + gallery)
- ✅ Project management
- ✅ Background processing

### Version 1.1 (Planned)
- 🚧 Face swap feature
- 🚧 Audio file upload
- 🚧 Video preview in app
- 🚧 Download to device

### Version 2.0 (Future)
- Custom voice training
- Video editing tools
- Template library
- Social media sharing
- Batch processing

---

**Built with ❤️ using Expo, FastAPI, and D-ID**
