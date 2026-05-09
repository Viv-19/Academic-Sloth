# Academic Sloth - Frontend Structure

This is the frontend structure for the **Academic Sloth** application, an AI-powered academic companion.

## 📁 Project Structure

```
Sloth_frontend/
└── public/
    ├── assets/
    │   ├── css/
    │   │   └── style.css          # Main stylesheet
    │   ├── images/                 # Image assets
    │   └── videos/                 # Video assets
    │
    ├── components/
    │   ├── background.html         # Background component
    │   ├── footer.html             # Footer component
    │   ├── glow.html               # Glow effect component
    │   └── header.html             # Header/navigation component
    │
    ├── js/
    │   ├── api.js                  # API communication module
    │   ├── chat.js                 # Chat functionality module
    │   ├── form.js                 # Form handling module
    │   ├── report.js               # Report display module
    │   └── ui.js                   # UI utilities module
    │
    ├── pages/
    │   ├── chat.html               # Chat interface page
    │   ├── insight_form.html       # Insight submission form
    │   ├── report.html             # Report display page
    │   └── splash.html             # Splash/loading screen
    │
    └── index.html                  # Main entry point
```

## 🚀 Features

- **Modern UI Design**: Dark theme with glassmorphism effects
- **Modular Architecture**: Reusable components and JavaScript modules
- **Responsive Design**: Works on desktop and mobile devices
- **API Integration**: Ready for backend connection
- **Component-Based**: HTML components loaded dynamically

## 📄 Pages

1. **Splash Page** (`pages/splash.html`)
   - Auto-redirects to index after 2 seconds
   - Loading animation

2. **Index/Home Page** (`index.html`)
   - Hero section with call-to-action buttons
   - Links to chat and insights pages

3. **Chat Page** (`pages/chat.html`)
   - Real-time chat interface
   - Message input and display
   - Session-based chat

4. **Insights Form** (`pages/insight_form.html`)
   - Form for submitting user insights
   - Validation included
   - Redirects to report on submission

5. **Report Page** (`pages/report.html`)
   - Displays generated reports
   - Dynamic content loading
   - User-specific data

## 🧩 Components

All components are loaded dynamically using the `ui.loadComponent()` function:

- **Background**: Visual background effects
- **Glow**: Animated glow effects
- **Header**: Navigation and branding
- **Footer**: Copyright and footer information

## 💻 JavaScript Modules

### `api.js`
Handles all backend API communication:
- `initSession()`: Initialize user session
- `sendMessage()`: Send chat messages
- `submitForm()`: Submit form data
- `getReport()`: Fetch user reports

### `chat.js`
Manages chat functionality:
- Session initialization
- Message sending/receiving
- UI updates

### `form.js`
Handles form operations:
- Form validation
- Submission handling
- Error display

### `report.js`
Manages report display:
- Data fetching
- Report rendering
- Section formatting

### `ui.js`
UI utility functions:
- Component loading
- Message display
- Loader management
- Error/success notifications

## 🎨 Styling

The project uses **vanilla CSS** with:
- Dark theme (#0f0f1e background)
- Glassmorphism effects (backdrop-filter)
- Gradient accents (purple to blue)
- Smooth animations
- Responsive breakpoints

## 🔧 Configuration

Update the API base URL in `js/api.js`:
```javascript
const API_BASE_URL = 'http://localhost:8000'; // Update with your backend URL
```

## 📝 Notes

- **No music components**: Music-related files excluded per requirements
- **Minimal dependencies**: Pure HTML, CSS, and JavaScript (ES6 modules)
- **Module-based**: Uses ES6 import/export syntax
- **Type="module"**: All scripts use type="module" for proper imports

## 🚦 Getting Started

1. Update the API_BASE_URL in `js/api.js` to point to your backend
2. Serve the `public` folder using any static file server
3. Access `splash.html` or `index.html` to start

## 📦 Next Steps

To complete the frontend:
1. Add actual backend integration
2. Populate images and videos in assets folders
3. Customize colors and branding
4. Add more interactive features as needed
