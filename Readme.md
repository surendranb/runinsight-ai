# AI Running Coach

## Description

The AI Running Coach is a web application designed to empower everyday runners to understand their running data and make informed decisions about their training.  It connects to your Strava account, analyzes your activities, and provides personalized feedback powered by the Gemini large language model.  The app uses Streamlit for the interactive interface and SQLite for local data storage.

## Key Features

*   **Strava Integration:** Securely connects to your Strava account to fetch your running activity data.
*   **AI-Powered Coaching:**  Provides personalized feedback and insights on your runs, leveraging the Gemini large language model. You can customize the prompts to request specific types of feedback or analysis.
*   **Actionable Insights:** Translates your raw running data into actionable insights across multiple tabs, covering pace, heart rate, distance, and recent run summaries.
*   **Progress Tracking:**  Tracks your progress over various time periods (7 days, 30 days, 90 days, year-to-date, last year, overall), summarizing key metrics like longest run, fastest pace, total distance, and running consistency.
*   **Goal Setting:** Allows you to set a narrative running goal, which personalizes the AI feedback.
*   **Data Synchronization:**  Easily sync new activities from Strava with a single click.
*   **Local Execution:** Runs locally on your laptop, ensuring data privacy.

## Technology Stack

*   **Python:** Core programming language for the application logic.
*   **Streamlit:**  Framework for building the interactive web application.
*   **SQLite:** Local database for storing running activity data and user goals.
*   **Gemini (via Google Generative AI API):**  Large language model used for generating personalized coaching feedback.
*   **stravalib:** Python library for interacting with the Strava API.
*   **NumPy:** Used for numerical calculations and analysis.

## Getting Started

1.  **Clone the repository:**
    ```bash
    git clone git@github.com:surendranb/ai-running-coach.git  # Replace with your repo URL
    cd ai-running-coach
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Create a `.env` file:**
    Create a `.env` file in the project's root directory and add your API keys:
    ```
    STRAVA_CLIENT_ID=YOUR_STRAVA_CLIENT_ID
    STRAVA_CLIENT_SECRET=YOUR_STRAVA_CLIENT_SECRET
    GEMINI_API_KEY=YOUR_GEMINI_API_KEY
    STRAVA_ACCESS_TOKEN=
    STRAVA_REFRESH_TOKEN=

    ```
4.  **Run `strava_data.py` to initialize the database and authenticate with Strava:**
    ```bash
    python strava_data.py
    ```
5.  **Run the Streamlit app:**
    ```bash
    streamlit run app.py
    ```
   When you run sync for the first time, you would see a 404 page. Copy the code and put it in the terminal to start the sync.

## Usage

1.  **Set Your Goal:**  Define your running goals in the sidebar. This helps personalize the AI feedback.
2.  **Sync Data:** Click "Sync Data" to fetch your latest activities from Strava. The sync doesn't handle API thresholds proactively yet. Mointor the terminal for errors and restart sync.
3.  **Explore:** Navigate the tabs to view recent runs, AI-powered insights on pace, heart rate, and distance, as well as overall progress summaries.
4.  **Customize AI Feedback (Advanced):**  Modify the prompts within the `generate_gemini_prompt_with_details` function in `app.py` to request specific insights or feedback from the AI.


## Future Considerations

*   Enhanced AI feedback with more detailed analysis and personalized training plans.
*   Integration with other fitness platforms and devices.
*   User accounts and cloud deployment.

## Contributing

Contributions are welcome!  Please open issues or submit pull requests.


## License

[MIT License](https://choosealicense.com/licenses/mit/)  (or specify your license)