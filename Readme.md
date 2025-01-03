# RunInsight AI 🏃‍♂️ Strava Data Analyzer

RunInsight AI analyzes your Strava running data alongside environmental conditions to help you understand what affects your performance. It combines running metrics, weather data, and AI-powered analysis to provide insights about your training.

## ✨ What it does now

### 📊 Performance Metrics
- Distance and pace analysis
- Heart rate monitoring and zones
- Elevation gain tracking
- Average and max speed calculations
- Cadence analysis
- Calories and effort score tracking

![Dashboard](https://preview.redd.it/built-something-to-analyse-strava-running-data-would-love-v0-6gee16wwoz9e1.png?width=1017&format=png&auto=webp&s=77f3cfa02bcf7d614218da86e01fa2a754867e99 "Preformance Analysis")


### 🌡️ Environmental Analysis
- Temperature and humidity impact
- Air quality (AQI and PM2.5) tracking
- Location-based performance comparison
- Weather condition correlation with performance

![Dashboard](https://preview.redd.it/built-something-to-analyse-strava-running-data-would-love-v0-5yw0zd4zoz9e1.png?width=1080&crop=smart&auto=webp&s=5d1fddbf28adfb27393c9cd9b918cb44f31e79d2 "Environmental Analysis")


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

![Dashboard](https://preview.redd.it/built-something-to-analyse-strava-running-data-would-love-v0-41fixi0voz9e1.png?width=1018&format=png&auto=webp&s=16f125029012a545e592c062911ecedccdb02b81 "AI Analysis")


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

4. **Sync the data**

1. Soon as you as you hit the sync button go back to the terminal.
2. Copy the Strava auth URL and paste it in a browser. Log in.
3. You'll see a 404 page (which is by design). Copy the code from the URL
4. Paste it back in the terminal to start the sync.

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
