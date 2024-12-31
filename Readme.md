# RunInsight AI 🏃‍♂️ Strava Data Analyzer

RunInsight AI analyzes your Strava running data alongside environmental conditions to help you understand what affects your performance. It combines running metrics, weather data, and AI-powered analysis to provide insights about your training.

## ✨ Current Features

### 📊 Performance Metrics
- Distance and pace analysis
- Heart rate monitoring and zones
- Elevation gain tracking
- Average and max speed calculations
- Cadence analysis
- Calories and effort score tracking

### 🌡️ Environmental Analysis
- Temperature and humidity impact
- Air quality (AQI and PM2.5) tracking
- Location-based performance comparison
- Weather condition correlation with performance

### 📈 Advanced Analytics
- Grade-adjusted pace metrics
- Pace variation analysis
- Running consistency patterns
- Split-by-split breakdowns
- Performance trends over time

### 🤖 AI Analysis
- Performance insights using Google's Gemini Pro model
- Pattern recognition in your running data
- Environmental impact analysis
- Training load observations

## What this isn't
- Process any other activity except running (at this point)
- Not a full blown coach (yet)

## 🚀 Getting Started

### Prerequisites
```plaintext
- Python 3.8+
- Strava account with API access
- OpenWeatherMap API key
- Google Cloud Project with Gemini API key
```

### Installation

1. **Clone and Install**
```bash
git clone https://github.com/yourusername/runinsight-ai.git
cd runinsight-ai
pip install -r requirements.txt
```

2. **Set Up Environment**
Create a `.env` file:
```env
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REFRESH_TOKEN=your_refresh_token
OPENWEATHERMAP_API_KEY=your_api_key
GEMINI_API_KEY=your_gemini_api_key
```

3. **Run the Application**
```bash
streamlit run app.py
```

## 💻 How It Works

1. **Data Collection**
   - Syncs with your Strava account to fetch running activities
   - Retrieves weather data from OpenWeatherMap
   - Stores data locally in SQLite database

2. **Analysis Features**
   - Calculates performance metrics over various time periods
   - Analyzes environmental impact on your running
   - Generates visualizations of trends and patterns
   - Provides AI-powered insights about your training

3. **Available Views**
   - Performance Metrics
   - Physiological Metrics
   - Elevation & Cadence Metrics
   - Environmental Metrics
   - Inferred Metrics
   - Deeper Insights
   - Activity Trends
   - AI Analysis

## 🔧 Technical Notes

- Built with Streamlit for the user interface
- Uses SQLite for local data storage
- Integrates with Strava and OpenWeatherMap APIs
- Employs Google's Gemini Pro for AI analysis
- All processing happens locally on your machine

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*RunInsight AI: Understanding your running through data*
